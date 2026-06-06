import threading
from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass
from typing import Optional, List, Dict
import itertools


# ---------------- Operations ----------------
class OpType(Enum):
    INSERT = "insert"
    DELETE = "delete"


@dataclass
class Operation:
    """A single edit. Carries everything needed to apply & transform it."""
    type: OpType
    pos: int
    text: str = ""
    length: int = 0
    author: str = ""
    base_version: int = 0
    op_id: int = 0

    def __post_init__(self):
        if self.type == OpType.INSERT:
            self.length = len(self.text)


# ---------------- Operational Transform ----------------
class OperationalTransform:
    """Transform op `a` so it applies cleanly AFTER concurrent committed op `b`.
    Returns a NEW transformed copy of `a`. Insert ties broken by author id."""

    @staticmethod
    def transform(a: Operation, b: Operation) -> Operation:
        if b.type == OpType.INSERT:
            return OperationalTransform._against_insert(a, b)
        return OperationalTransform._against_delete(a, b)

    @staticmethod
    def _shift(op: Operation, delta: int) -> Operation:
        return Operation(op.type, op.pos + delta, op.text, op.length,
                         op.author, op.base_version, op.op_id)

    @staticmethod
    def _against_insert(a: Operation, b: Operation) -> Operation:
        if b.pos < a.pos or (b.pos == a.pos and b.author < a.author):
            return OperationalTransform._shift(a, b.length)
        return OperationalTransform._shift(a, 0)

    @staticmethod
    def _against_delete(a: Operation, b: Operation) -> Operation:
        b_end = b.pos + b.length
        if a.pos >= b_end:
            return OperationalTransform._shift(a, -b.length)
        if a.pos < b.pos:
            return OperationalTransform._shift(a, 0)
        return OperationalTransform._shift(a, b.pos - a.pos)


# ---------------- Document content ----------------
class DocumentContent:
    """In-memory text buffer. (Gap buffer / piece-table in production.)"""

    def __init__(self, text: str = ""):
        self._buf: List[str] = list(text)

    def apply(self, op: Operation) -> None:
        if op.type == OpType.INSERT:
            if op.pos < 0 or op.pos > len(self._buf):
                raise ValueError(f"insert pos {op.pos} out of range")
            self._buf[op.pos:op.pos] = list(op.text)
        else:
            if op.pos < 0 or op.pos + op.length > len(self._buf):
                raise ValueError("delete range out of bounds")
            del self._buf[op.pos:op.pos + op.length]

    def text(self) -> str:
        return "".join(self._buf)

    def __len__(self):
        return len(self._buf)


# ---------------- Observer for live updates ----------------
class DocumentObserver(ABC):
    @abstractmethod
    def on_operation(self, doc_id: str, op: Operation, version: int) -> None: ...


# ---------------- Server-side document session ----------------
class DocumentSession:
    """Authoritative server copy. Owns version history, applies & rebroadcasts
    transformed ops. Thread-safe via a reentrant lock."""

    def __init__(self, doc_id: str, initial: str = ""):
        self.doc_id = doc_id
        self.content = DocumentContent(initial)
        self.version = 0
        self.history: List[Operation] = []
        self._observers: Dict[str, DocumentObserver] = {}
        self._lock = threading.RLock()

    def subscribe(self, user_id: str, obs: DocumentObserver) -> None:
        with self._lock:
            self._observers[user_id] = obs

    def unsubscribe(self, user_id: str) -> None:
        with self._lock:
            self._observers.pop(user_id, None)

    def receive(self, op: Operation) -> Operation:
        """Transform a client op against everything committed since its
        base_version, apply, bump version, broadcast. ALWAYS returns the
        committed (transformed) op so the sender can converge."""
        with self._lock:
            if op.base_version > self.version:
                raise ValueError("op from the future")
            transformed = op
            for past in self.history[op.base_version:]:
                transformed = OperationalTransform.transform(transformed, past)
            self.content.apply(transformed)
            self.history.append(transformed)
            self.version += 1
            transformed.base_version = self.version
            self._broadcast(transformed)
            return transformed

    def _broadcast(self, op: Operation) -> None:
        for uid, obs in list(self._observers.items()):
            if uid != op.author:
                obs.on_operation(self.doc_id, op, self.version)


# ---------------- Cursor / selection ----------------
@dataclass
class Cursor:
    user_id: str
    pos: int = 0
    anchor: Optional[int] = None  # selection start; None => no selection

    def has_selection(self) -> bool:
        return self.anchor is not None and self.anchor != self.pos

    def transform(self, op: Operation) -> None:
        """Keep this user's caret stable when others edit before it."""
        if op.type == OpType.INSERT and op.pos <= self.pos:
            self.pos += op.length
        elif op.type == OpType.DELETE and op.pos < self.pos:
            self.pos -= min(op.length, self.pos - op.pos)


# ---------------- Client session ----------------
class ClientSession(DocumentObserver):
    """A user's local replica. Edits locally, sends to server, applies remote
    ops, and keeps the cursor consistent."""

    _ids = itertools.count(1)

    def __init__(self, user_id: str, server: "DocumentServer", doc_id: str):
        self.user_id = user_id
        self.server = server
        self.doc_id = doc_id
        self.local = DocumentContent(server.snapshot(doc_id))
        self.version = server.version_of(doc_id)
        self.cursor = Cursor(user_id, pos=len(self.local))
        self._lock = threading.RLock()
        server.session(doc_id).subscribe(user_id, self)

    def edit_insert(self, pos: int, text: str) -> None:
        self._send(Operation(OpType.INSERT, pos, text=text, author=self.user_id,
                             base_version=self.version, op_id=next(self._ids)))

    def edit_delete(self, pos: int, length: int) -> None:
        self._send(Operation(OpType.DELETE, pos, length=length, author=self.user_id,
                             base_version=self.version, op_id=next(self._ids)))

    def _send(self, op: Operation) -> None:
        committed = self.server.submit(self.doc_id, op)
        with self._lock:
            self.local.apply(committed)
            self.version = committed.base_version
            self.cursor.transform(committed)

    def on_operation(self, doc_id: str, op: Operation, version: int) -> None:
        with self._lock:
            self.local.apply(op)
            self.version = version
            self.cursor.transform(op)

    def text(self) -> str:
        return self.local.text()


# ---------------- Passive replica (for testing convergence) ----------------
class ReplicaObserver(DocumentObserver):
    def __init__(self, name: str, initial: str):
        self.name = name
        self.content = DocumentContent(initial)

    def on_operation(self, doc_id: str, op: Operation, version: int) -> None:
        self.content.apply(op)

    def text(self):
        return self.content.text()


# ---------------- Server facade ----------------
class DocumentServer:
    def __init__(self):
        self._docs: Dict[str, DocumentSession] = {}
        self._lock = threading.RLock()

    def create(self, doc_id: str, initial: str = "") -> None:
        with self._lock:
            if doc_id in self._docs:
                raise ValueError("doc exists")
            self._docs[doc_id] = DocumentSession(doc_id, initial)

    def session(self, doc_id: str) -> DocumentSession:
        with self._lock:
            if doc_id not in self._docs:
                raise KeyError("no such doc")
            return self._docs[doc_id]

    def submit(self, doc_id: str, op: Operation) -> Operation:
        return self.session(doc_id).receive(op)

    def snapshot(self, doc_id: str) -> str:
        return self.session(doc_id).content.text()

    def version_of(self, doc_id: str) -> int:
        return self.session(doc_id).version


# ---------------- Driver ----------------
if __name__ == "__main__":
    server = DocumentServer()
    server.create("d1", "Hello")

    # Two passive replicas that receive EVERY op (different ids than authors).
    r1, r2 = ReplicaObserver("r1", "Hello"), ReplicaObserver("r2", "Hello")
    server.session("d1").subscribe("r1", r1)
    server.session("d1").subscribe("r2", r2)

    # 1. CONCURRENT inserts at the SAME position, both authored vs version 0.
    a = Operation(OpType.INSERT, 5, text=" Alice", author="alice", base_version=0)
    b = Operation(OpType.INSERT, 5, text=" Bob", author="bob", base_version=0)
    server.submit("d1", a)
    server.submit("d1", b)
    s = server.snapshot("d1")
    print("server:", repr(s))
    assert " Alice" in s and " Bob" in s         # no lost update
    assert r1.text() == r2.text() == s            # all replicas converge

    # 2. boundary: invalid insert position rejected
    try:
        server.submit("d1", Operation(OpType.INSERT, 999, text="x",
                      author="alice", base_version=server.version_of("d1")))
        assert False
    except ValueError:
        pass

    # 3. unknown doc rejected
    try:
        server.snapshot("ghost"); assert False
    except KeyError:
        pass

    # 4. duplicate doc creation rejected
    try:
        server.create("d1"); assert False
    except ValueError:
        pass

    # 5. concurrent insert vs delete of overlapping range
    server.submit("d1", Operation(OpType.DELETE, 0, length=5, author="carol",
                  base_version=server.version_of("d1")))   # delete "Hello"
    assert r1.text() == r2.text() == server.snapshot("d1")

    # 6. op from the future rejected
    try:
        server.submit("d1", Operation(OpType.INSERT, 0, text="z",
                      author="x", base_version=999)); assert False
    except ValueError:
        pass

    # 7. live ClientSession with cursor tracking
    dave = ClientSession("dave", server, "d1")
    start = dave.cursor.pos
    # someone else inserts before dave's caret -> caret should shift right
    server.submit("d1", Operation(OpType.INSERT, 0, text="XYZ", author="eve",
                  base_version=server.version_of("d1")))
    assert dave.cursor.pos == start + 3, dave.cursor.pos
    assert dave.text() == server.snapshot("d1")

    print("final:", repr(server.snapshot("d1")))
    print("ALL ASSERTIONS PASSED")
