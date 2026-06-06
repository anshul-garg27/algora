from enum import Enum


class NodeType(Enum):
    DIRECTORY = "dir"
    FILE = "file"


class Node:
    def __init__(self, name, ntype=NodeType.DIRECTORY, parent=None):
        self.name = name
        self.type = ntype
        self.parent = parent
        self.children = {}

    def is_dir(self):
        return self.type == NodeType.DIRECTORY

    def abs_path(self):
        if self.parent is None:
            return "/"
        parts = []
        node = self
        while node.parent is not None:
            parts.append(node.name)
            node = node.parent
        return "/" + "/".join(reversed(parts))


class FileSystem:
    def __init__(self, wildcard_picker=None):
        self.root = Node("", NodeType.DIRECTORY, parent=None)
        self.cwd = self.root
        self.wildcard_picker = wildcard_picker or (
            lambda opts: sorted(opts, key=lambda n: n.name)[0]
        )

    @staticmethod
    def _split(path):
        if path is None or path == "":
            raise ValueError("empty path")
        if len(path) > 100:
            raise ValueError("path too long")
        absolute = path.startswith("/")
        comps = [c for c in path.split("/") if c != ""]
        return absolute, comps

    def _start_node(self, absolute):
        return self.root if absolute else self.cwd

    def _step(self, node, comp):
        if comp == ".":
            return node
        if comp == "..":
            return node.parent if node.parent is not None else node
        child = node.children.get(comp)
        if child is not None and child.is_dir():
            return child
        return None

    def mkdir(self, path):
        try:
            absolute, comps = self._split(path)
        except ValueError:
            return False
        if "*" in path:
            return False
        node = self._start_node(absolute)
        for comp in comps:
            if comp == ".":
                continue
            if comp == "..":
                node = node.parent if node.parent is not None else node
                continue
            nxt = node.children.get(comp)
            if nxt is None:
                nxt = Node(comp, NodeType.DIRECTORY, parent=node)
                node.children[comp] = nxt
            elif not nxt.is_dir():
                return False
            node = nxt
        return True

    def pwd(self):
        return self.cwd.abs_path()

    def cd(self, path):
        target = self._resolve(path)
        if target is None:
            return False
        self.cwd = target
        return True

    def _resolve(self, path):
        try:
            absolute, comps = self._split(path)
        except ValueError:
            return None
        frontier = [self._start_node(absolute)]
        for comp in comps:
            nxt_nodes = {}
            if comp == "*":
                for node in frontier:
                    for cand in self._wildcard_matches(node):
                        nxt_nodes[id(cand)] = cand
            else:
                for node in frontier:
                    s = self._step(node, comp)
                    if s is not None:
                        nxt_nodes[id(s)] = s
            if not nxt_nodes:
                return None
            frontier = list(nxt_nodes.values())
        if not frontier:
            return None
        if len(frontier) == 1:
            return frontier[0]
        return self.wildcard_picker(frontier)

    def _wildcard_matches(self, node):
        # '*' matches any child DIRECTORY. (We exclude '.'/'..' so that
        # examples like  cd /a/*  deterministically descend into a child.)
        return [c for c in node.children.values() if c.is_dir()]


# Inject a file to test the "file blocks mkdir" path
def _add_file(fs, parent_path_node, name):
    parent_path_node.children[name] = Node(name, NodeType.FILE, parent=parent_path_node)


if __name__ == "__main__":
    fs = FileSystem()

    # Example 1
    assert fs.mkdir("/a/b") is True
    assert fs.cd("/a/*") is True
    assert fs.pwd() == "/a/b"

    # Example 2 (deterministic: lexicographically smallest -> bar)
    fs2 = FileSystem()
    assert fs2.mkdir("/foo/bar") is True
    assert fs2.mkdir("/foo/baz") is True
    assert fs2.cd("/foo/*") is True
    assert fs2.pwd() == "/foo/bar"

    # pwd at root
    fs3 = FileSystem()
    assert fs3.pwd() == "/"

    # relative cd, . and ..
    fs3.mkdir("/x/y/z")
    assert fs3.cd("x/y") is True
    assert fs3.pwd() == "/x/y"
    assert fs3.cd("./z") is True
    assert fs3.pwd() == "/x/y/z"
    assert fs3.cd("../..") is True
    assert fs3.pwd() == "/x"

    # .. at root stays root
    assert fs3.cd("/") is True
    assert fs3.cd("..") is True
    assert fs3.pwd() == "/"

    # INVALID path -> cwd unchanged (atomic)
    fs3.cd("/x")
    assert fs3.cd("/x/nope/deep") is False
    assert fs3.pwd() == "/x"

    # cd /x/* -> only child 'y' matches the wildcard
    assert fs3.cd("/x/*") is True
    assert fs3.pwd() == "/x/y"
    # wildcard with NO child match -> fail, cwd unchanged
    assert fs3.cd("/x/y/z") is True
    assert fs3.cd("z/*") is False
    assert fs3.pwd() == "/x/y/z"

    # file blocks mkdir
    fs4 = FileSystem()
    fs4.mkdir("/data")
    _add_file(fs4, fs4.root.children["data"], "f")
    assert fs4.mkdir("/data/f/sub") is False   # 'f' is a file
    assert fs4.mkdir("/data/g") is True

    # boundary: empty + too long + wildcard-in-mkdir
    assert fs4.mkdir("") is False
    assert fs4.mkdir("/a" * 60) is False  # >100 chars
    assert fs4.mkdir("/a/*/b") is False

    # unknown id / cd to nonexistent
    assert fs4.cd("/zzz") is False

    print("ALL ASSERTIONS PASSED")
    # demo of stated examples
    demo = FileSystem()
    print(demo.mkdir("/a/b"))
    print(demo.cd("/a/*"))
    print(demo.pwd())
