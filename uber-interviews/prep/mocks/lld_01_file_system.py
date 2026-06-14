"""
UBER MACHINE CODING / LLD MOCK #1 — 45 minutes
================================================
(Asked 4x in the last 12 months, including in a May-2026 offer loop.)

Design and implement a set of basic file system APIs that simulate common
directory operations:

  * mkdir(path) -> bool
      Creates a directory at the absolute path. Intermediate directories
      are created if they don't exist. Returns True if successful,
      False otherwise (e.g., path is invalid).

  * pwd() -> str
      Returns the current working directory as an absolute path.
      Root is '/'.

  * cd(path) -> bool
      Changes the current working directory. Must support:
        - absolute paths:  cd('/a/b')
        - relative paths:  cd('b/c')
        - '..' and '.':    cd('../x')
        - WILDCARD '*' matching a single path segment: cd('/a/*/c')
          -> succeeds if exactly one directory matches the pattern;
             if zero or multiple directories match, return False and
             stay where you are.
      Returns True on success, False otherwise (no partial moves).

Expectations (this is how you'll be graded):
  1. RUNNABLE code — the demo below must execute and print PASS.
  2. Clean OOP: clear class boundaries, a real tree structure.
  3. Edge cases: bad paths, cd above root, trailing slashes, etc.
  4. Be ready for follow-up questions after time is up.

Rules of the mock:
  - 45 minutes from start. Write everything in this file.
  - You may add more tests of your own.
  - When done (or time up), say "done" in the chat.
"""

# ============== YOUR IMPLEMENTATION BELOW ==============


class FileSystem:
    pass  # replace with your design


# ============== DEMO / ACCEPTANCE TESTS ==============

def main() -> None:
    fs = FileSystem()

    assert fs.pwd() == "/"
    assert fs.mkdir("/a/b/c") is True          # creates intermediates
    assert fs.mkdir("/a/b2/c") is True
    assert fs.cd("/a/b") is True
    assert fs.pwd() == "/a/b"
    assert fs.cd("c") is True                  # relative
    assert fs.pwd() == "/a/b/c"
    assert fs.cd("../../b2") is True           # .. handling
    assert fs.pwd() == "/a/b2"
    assert fs.cd("/a/*/c") is False            # wildcard ambiguous: b and b2 both have c
    assert fs.pwd() == "/a/b2"                 # no partial move
    assert fs.mkdir("/a/b/unique") is True
    assert fs.cd("/a/*/unique") is True        # exactly one match -> /a/b/unique
    assert fs.pwd() == "/a/b/unique"
    assert fs.cd("/nope/x") is False
    assert fs.cd("..") is True
    assert fs.pwd() == "/a/b"

    print("PASS")


if __name__ == "__main__":
    main()
