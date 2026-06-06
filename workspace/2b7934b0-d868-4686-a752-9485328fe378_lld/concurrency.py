"""§9 second iteration: a thread-safe ExpenseManager + a race test.

The clean §6 ExpenseManager is single-threaded-correct. Its `_add_debt` is a
read-modify-write on a shared dict (`balance[a][b] += cents`), and `add_expense`
is a check-then-act (duplicate check, then insert). Under threads these race and
lose updates. We wrap every public mutator/reader in ONE reentrant lock.
"""
from __future__ import annotations

import threading
from typing import Dict

from expense_manager import ExpenseManager
from models import SplitType, User


class ThreadSafeExpenseManager(ExpenseManager):
    """Coarse single-RLock guard. RLock (reentrant) because public methods may
    call other guarded helpers, and we never want a thread to deadlock on itself.
    One lock keeps the whole ledger consistent; per-user locks would need careful
    lock ordering to avoid deadlock when a single expense touches many users."""

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.RLock()

    def add_expense(self, *args, **kwargs):
        with self._lock:
            return super().add_expense(*args, **kwargs)

    def settle(self, *args, **kwargs):
        with self._lock:
            return super().settle(*args, **kwargs)

    def get_balance(self, a: str, b: str) -> int:
        with self._lock:  # reads take the lock too -> never see a half-applied expense
            return super().get_balance(a, b)

    def get_balances(self, user_id: str) -> Dict[str, int]:
        with self._lock:
            return dict(super().get_balances(user_id))


def race_test() -> None:
    m = ThreadSafeExpenseManager()
    m.add_user(User("u1", "Alice", "a@x.com"))
    m.add_user(User("u2", "Bob", "b@x.com"))

    N = 200
    barrier = threading.Barrier(N)

    def worker(i: int) -> None:
        barrier.wait()  # maximize contention: all start together
        # Each: $10 expense paid by u1, split equally -> Bob owes Alice 500c.
        m.add_expense(f"e{i}", "x", 10.00, "u1", SplitType.EQUAL, ["u1", "u2"])

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(N)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Exactly N expenses each adding 500c -> Bob owes Alice 200 * 500 = 100000c.
    assert m.get_balance("u2", "u1") == N * 500, m.get_balance("u2", "u1")
    assert m.get_balance("u1", "u2") == -(N * 500)  # antisymmetry survives the race
    print(f"Race test: {N} threads, Bob owes Alice ${m.get_balance('u2','u1')/100:.2f} (expected ${N*500/100:.2f}) -- no lost updates.")


if __name__ == "__main__":
    race_test()
