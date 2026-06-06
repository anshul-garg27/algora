"""Driver: exercises happy paths, boundary/invalid inputs, and concurrency."""
from __future__ import annotations

import threading
from decimal import Decimal

from manager import ExpenseManager
from models import (
    DuplicateError,
    InvalidExpenseError,
    InvalidSplitError,
    SplitType,
    UnknownUserError,
    User,
)

D = Decimal


def setup() -> ExpenseManager:
    m = ExpenseManager()
    for uid, name in [("u1", "Alice"), ("u2", "Bob"), ("u3", "Carol")]:
        m.add_user(User(uid, name, f"{name.lower()}@x.com"))
    return m


def test_equal_split_with_rounding():
    m = setup()
    # 100 / 3 -> 33.34, 33.33, 33.33 (drift goes to first); Alice paid.
    m.add_expense("e1", "Dinner", D("100"), "u1", ["u1", "u2", "u3"],
                  SplitType.EQUAL)
    assert m.get_balances("u1") == {"u2": D("33.33"), "u3": D("33.33")}
    assert m.get_balances("u2") == {"u1": D("-33.33")}
    print("equal+rounding OK:", m.get_balances("u1"))


def test_exact_and_percent():
    m = setup()
    m.add_expense("e1", "Cab", D("90"), "u2", ["u1", "u3"], SplitType.EXACT,
                  [D("40"), D("50")])
    assert m.get_balances("u2") == {"u1": D("40"), "u3": D("50")}

    m.add_expense("e2", "Hotel", D("300"), "u1", ["u1", "u2", "u3"],
                  SplitType.PERCENT, [D("50"), D("25"), D("25")])
    # Alice paid 300, owes herself 150 (ignored); Bob 75, Carol 75.
    assert m.get_balances("u1")["u2"] == D("75") + D("-40")  # netted with e1
    print("exact+percent OK:", m.get_balances("u1"))


def test_invalid_inputs():
    m = setup()
    # unknown user
    try:
        m.add_expense("e1", "x", D("10"), "ghost", ["u1"], SplitType.EQUAL)
        assert False
    except UnknownUserError:
        pass
    # negative amount
    try:
        m.add_expense("e2", "x", D("-5"), "u1", ["u2"], SplitType.EQUAL)
        assert False
    except InvalidExpenseError:
        pass
    # exact amounts that do not sum to total
    try:
        m.add_expense("e3", "x", D("100"), "u1", ["u2", "u3"],
                      SplitType.EXACT, [D("40"), D("40")])
        assert False
    except InvalidSplitError:
        pass
    # percentages not summing to 100
    try:
        m.add_expense("e4", "x", D("100"), "u1", ["u2", "u3"],
                      SplitType.PERCENT, [D("60"), D("30")])
        assert False
    except InvalidSplitError:
        pass
    # duplicate expense id
    m.add_expense("e5", "ok", D("10"), "u1", ["u2"], SplitType.EQUAL)
    try:
        m.add_expense("e5", "dup", D("10"), "u1", ["u2"], SplitType.EQUAL)
        assert False
    except DuplicateError:
        pass
    print("invalid-input rejection OK")


def test_settle_up():
    m = setup()
    m.add_expense("e1", "Lunch", D("60"), "u1", ["u1", "u2"], SplitType.EQUAL)
    assert m.get_balances("u2") == {"u1": D("-30")}  # Bob owes Alice 30
    m.settle_up("u2", "u1", D("30"))                  # Bob pays Alice back
    assert m.get_balances("u2") == {}                 # square
    print("settle-up OK")


def test_concurrency_no_lost_update():
    # 100 threads each add a 1.00 expense Bob owes Alice -> Alice owed exactly 100.
    m = setup()
    def worker(i):
        m.add_expense(f"c{i}", "x", D("1.00"), "u1", ["u2"], SplitType.EQUAL)
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(100)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert m.get_balances("u1") == {"u2": D("100.00")}, m.get_balances("u1")
    print("concurrency (no lost update) OK:", m.get_balances("u1"))


def test_simplify():
    m = setup()
    # Alice paid 30 split equally with Bob -> Bob owes Alice 15.
    m.add_expense("e1", "a", D("30"), "u1", ["u1", "u2"], SplitType.EQUAL)
    # Bob paid 30 split equally with Carol -> Carol owes Bob 15.
    m.add_expense("e2", "b", D("30"), "u2", ["u2", "u3"], SplitType.EQUAL)
    txns = m.simplify_group(["u1", "u2", "u3"])
    # Net: Bob is square, Carol owes Alice 15 -> single transfer.
    assert txns == [("u3", "u1", D("15"))], txns
    print("debt simplification OK:", txns)


if __name__ == "__main__":
    test_equal_split_with_rounding()
    test_exact_and_percent()
    test_invalid_inputs()
    test_settle_up()
    test_concurrency_no_lost_update()
    test_simplify()
    print("\nALL TESTS PASSED")
