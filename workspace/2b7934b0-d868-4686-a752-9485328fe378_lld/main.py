"""Driver + assertions exercising tricky cases (single-threaded, clean core)."""
from expense_manager import ExpenseManager
from models import (
    DuplicateExpenseError,
    InvalidAmountError,
    InvalidSplitError,
    SplitType,
    User,
    UserNotFoundError,
)


def fmt(cents: int) -> str:
    return f"${cents / 100:.2f}"


def main() -> None:
    m = ExpenseManager()
    for uid, name in [("u1", "Alice"), ("u2", "Bob"), ("u3", "Carol")]:
        m.add_user(User(uid, name, f"{name.lower()}@x.com"))

    # 1. EQUAL split with a rounding remainder: $10.00 / 3 = 333,333,334 cents.
    m.add_expense("e1", "Lunch", 10.00, "u1", SplitType.EQUAL, ["u1", "u2", "u3"])
    # Alice paid 1000c; she keeps her 334c share, Bob owes 333, Carol owes 333.
    assert m.get_balance("u2", "u1") == 333, m.get_balance("u2", "u1")
    assert m.get_balance("u3", "u1") == 333
    # No penny lost: shares 334+333+333 == 1000.
    assert m.get_balance("u1", "u2") == -333  # antisymmetry

    # 2. EXACT split that sums correctly.
    m.add_expense("e2", "Cab", 30.00, "u2", SplitType.EXACT, ["u1", "u2", "u3"],
                  values=[10.0, 5.0, 15.0])
    # u1 owes u2 1000c, u3 owes u2 1500c.
    assert m.get_balance("u1", "u2") == 1000 - 333  # net with e1
    assert m.get_balance("u3", "u2") == 1500

    # 3. PERCENT split.
    m.add_expense("e3", "Hotel", 100.00, "u3", SplitType.PERCENT, ["u1", "u2", "u3"],
                  values=[50.0, 30.0, 20.0])
    # Balances accumulate: u1<->u3 was -333 (e1), now +5000 -> 4667.
    assert m.get_balance("u1", "u3") == 5000 - 333, m.get_balance("u1", "u3")
    # u2<->u3 was -1500 (e2 cab), now +3000 -> 1500.
    assert m.get_balance("u2", "u3") == 3000 - 1500, m.get_balance("u2", "u3")

    # 4. Settlement reduces what Bob owes Alice by exactly the paid amount.
    before = m.get_balance("u2", "u1")
    m.settle("u2", "u1", 3.33)  # Bob pays Alice $3.33 (333c)
    assert m.get_balance("u2", "u1") == before - 333, m.get_balance("u2", "u1")
    assert m.get_balance("u1", "u2") == -(before - 333)  # antisymmetry holds

    # --- Edge cases: every bad input has a defined outcome ---
    def expect(err, fn):
        try:
            fn()
        except err:
            return
        raise AssertionError(f"expected {err.__name__}")

    expect(InvalidAmountError,
           lambda: m.add_expense("eX", "neg", -5, "u1", SplitType.EQUAL, ["u1", "u2"]))
    expect(UserNotFoundError,
           lambda: m.add_expense("eX", "ghost", 5, "u1", SplitType.EQUAL, ["u1", "ghost"]))
    expect(DuplicateExpenseError,
           lambda: m.add_expense("e1", "dup", 5, "u1", SplitType.EQUAL, ["u1", "u2"]))
    expect(InvalidSplitError,
           lambda: m.add_expense("eY", "bad%", 10, "u1", SplitType.PERCENT,
                                 ["u1", "u2"], values=[40.0, 40.0]))
    expect(InvalidSplitError,
           lambda: m.add_expense("eZ", "badexact", 10, "u1", SplitType.EXACT,
                                 ["u1", "u2"], values=[3.0, 5.0]))

    print("Alice balances:", {k: fmt(v) for k, v in m.get_balances("u1").items()})
    print("Bob balances:  ", {k: fmt(v) for k, v in m.get_balances("u2").items()})
    print("Carol balances:", {k: fmt(v) for k, v in m.get_balances("u3").items()})
    print("All single-threaded assertions passed.")


if __name__ == "__main__":
    main()
