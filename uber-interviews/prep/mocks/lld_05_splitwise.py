"""
UBER MACHINE CODING / LLD MOCK #5 — 45 minutes — Splitwise
============================================================
(Asked at Uber as HLD with LLD core (May-2026 offer loop: "Design Splitwise,
focus on the graph edge optimization") and Uber Eats pricing-calculator
variants. This mock is the LLD layer: working balance engine.)

Build an expense-sharing engine:

  * add_user(uid)
  * add_expense(paid_by, amount, participants, split_type, split_data=None)
      split_type: "EQUAL"            -> equal shares (handle paise/rounding!)
                  "EXACT"            -> split_data = {uid: amount} (must sum)
                  "PERCENT"          -> split_data = {uid: pct} (must sum 100)
  * balances() -> dict of net balance per user (+ = others owe them)
  * owes(uid) -> dict {other_uid: amount} simplified pairwise view
  * settle_up() -> list of (debtor, creditor, amount) transactions that
      zero everyone out, MINIMIZING the number of transactions (greedy
      max-debtor -> max-creditor matching is the expected approach).

Expectations:
  1. RUNNABLE — demo below must print PASS.
  2. Money handling: use integer paise/cents internally; rounding leftover
     on EQUAL goes to the payer (state your convention!).
  3. Validation: EXACT must sum to amount; PERCENT to 100; unknown users.
  4. settle_up correctness > cleverness (greedy is fine; optimal min-cash-flow
     is NP-hard in general — knowing that is a bonus point).

When done (or at 45 min), say "done" to the interviewer chat.
"""

# ============== YOUR IMPLEMENTATION BELOW ==============


class Splitwise:
    pass  # replace with your design


# ============== DEMO / ACCEPTANCE TESTS ==============

def main() -> None:
    s = Splitwise()
    for u in ("u1", "u2", "u3", "u4"):
        s.add_user(u)

    # u1 pays 1000 equally among 4 -> each owes 250
    s.add_expense("u1", 1000.00, ["u1", "u2", "u3", "u4"], "EQUAL")
    b = s.balances()
    assert round(b["u1"], 2) == 750.00 and round(b["u2"], 2) == -250.00

    # EXACT split
    s.add_expense("u2", 300.00, ["u1", "u3"], "EXACT",
                  {"u1": 100.00, "u3": 200.00})
    b = s.balances()
    assert round(b["u2"], 2) == 50.00          # -250 + 300
    assert round(b["u1"], 2) == 650.00         # 750 - 100

    # PERCENT split with rounding (1/3 style): 100 at 33.33/33.33/33.34
    s.add_expense("u3", 100.00, ["u1", "u2", "u3"], "PERCENT",
                  {"u1": 33.33, "u2": 33.33, "u3": 33.34})

    # invalid splits must raise
    try:
        s.add_expense("u1", 100, ["u2"], "EXACT", {"u2": 99})
        raise AssertionError("EXACT not summing must raise")
    except ValueError:
        pass

    # settlement zeroes everyone with few transactions
    txns = s.settle_up()
    net = {u: 0.0 for u in ("u1", "u2", "u3", "u4")}
    for debtor, creditor, amt in txns:
        assert amt > 0
        net[debtor] += amt
        net[creditor] -= amt
    b = s.balances()
    for u in net:
        assert abs(b[u] - net[u]) < 0.01, (u, b[u], net[u])
    assert len(txns) <= 3                      # n users -> <= n-1 transactions

    print("PASS")


if __name__ == "__main__":
    main()
