"""Driver + assertions exercising tricky cases."""
import threading

from models import User, Group, Expense, Split, SplitType
from service import ExpenseManager


class PrintNotifier:
    def on_expense(self, expense):
        print(f"[notify] '{expense.description}' ${expense.amount:.2f} paid by {expense.paid_by}")


def fresh(users=("alice", "bob", "carol"), notify=False):
    mgr = ExpenseManager()
    for uid in users:
        mgr.add_user(User(uid, uid.title()))
    mgr.add_group(Group("g1", "Trip", list(users)))
    if notify:
        mgr.register_observer(PrintNotifier())
    return mgr


def test_equal():
    mgr = fresh(notify=True)
    # Alice pays $90 for all 3 -> bob & carol each owe 30
    mgr.add_expense(Expense("e1", "Dinner", 90.0, "alice", SplitType.EQUAL,
                            [Split("alice"), Split("bob"), Split("carol")], "g1"))
    assert abs(mgr.owes("bob", "alice") - 30.0) < 0.01
    assert abs(mgr.owes("carol", "alice") - 30.0) < 0.01


def test_exact():
    mgr = fresh()
    # Bob pays $50; alice owes 20, bob 10, carol 20
    mgr.add_expense(Expense("e2", "Cab", 50.0, "bob", SplitType.EXACT,
                            [Split("alice", amount=20), Split("bob", amount=10),
                             Split("carol", amount=20)]))
    assert abs(mgr.owes("alice", "bob") - 20.0) < 0.01
    assert abs(mgr.owes("carol", "bob") - 20.0) < 0.01


def test_percent_rounding():
    mgr = fresh()
    # Carol pays $100 split 33.33 / 33.33 / 33.34 -> owed must sum to exactly 100
    mgr.add_expense(Expense("e3", "Hotel", 100.0, "carol", SplitType.PERCENT,
                            [Split("alice", percent=33.33), Split("bob", percent=33.33),
                             Split("carol", percent=33.34)]))
    alice = mgr.owes("alice", "carol")
    bob = mgr.owes("bob", "carol")
    assert abs(alice - 33.33) < 0.01 and abs(bob - 33.33) < 0.01
    # carol's own 33.34 stays with her (payer); total collected from others == 66.66
    assert abs(alice + bob - 66.66) < 0.01


def test_netting_and_settle():
    mgr = fresh()
    # Dinner: bob owes alice 30
    mgr.add_expense(Expense("e1", "Dinner", 90.0, "alice", SplitType.EQUAL,
                            [Split("alice"), Split("bob"), Split("carol")]))
    # Cab: alice owes bob 20 -> nets to bob owes alice 10
    mgr.add_expense(Expense("e2", "Cab", 50.0, "bob", SplitType.EXACT,
                            [Split("alice", amount=20), Split("bob", amount=10),
                             Split("carol", amount=20)]))
    assert abs(mgr.owes("bob", "alice") - 10.0) < 0.01, mgr.owes("bob", "alice")
    # Bob settles the remaining 10 -> balance zero
    mgr.settle("bob", "alice", 10.0)
    assert abs(mgr.owes("bob", "alice")) < 0.01


def test_boundaries():
    mgr = fresh()
    cases = [
        lambda: Expense("x", "bad", -10, "alice", SplitType.EQUAL, [Split("alice")]),          # negative amount
        lambda: mgr.add_expense(Expense("x2", "bad", 100, "alice", SplitType.EXACT,
                 [Split("alice", amount=40), Split("bob", amount=40)])),                        # exact != total
        lambda: mgr.add_expense(Expense("x3", "bad", 100, "alice", SplitType.PERCENT,
                 [Split("alice", percent=50), Split("bob", percent=40)])),                      # percent != 100
        lambda: mgr.add_expense(Expense("x4", "bad", 10, "ghost", SplitType.EQUAL, [Split("ghost")])),  # unknown user
        lambda: mgr.add_expense(Expense("x5", "bad", 10, "alice", SplitType.EQUAL,
                 [Split("alice"), Split("alice")])),                                            # duplicate participant
    ]
    for c in cases:
        try:
            c()
            assert False, "expected ValueError"
        except ValueError:
            pass

    # duplicate expense id
    mgr.add_expense(Expense("dup", "ok", 10, "alice", SplitType.EQUAL, [Split("alice"), Split("bob")]))
    try:
        mgr.add_expense(Expense("dup", "again", 10, "alice", SplitType.EQUAL, [Split("alice")]))
        assert False
    except ValueError:
        pass


def test_concurrency():
    mgr = fresh(users=("alice", "bob"))
    # 100 concurrent $10 equal expenses alice pays -> bob owes 5 each = 500
    def worker(i):
        mgr.add_expense(Expense(f"c{i}", "concurrent", 10.0, "alice", SplitType.EQUAL,
                                [Split("alice"), Split("bob")]))
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(100)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert abs(mgr.owes("bob", "alice") - 500.0) < 0.01, mgr.owes("bob", "alice")


def main():
    test_equal()
    test_exact()
    test_percent_rounding()
    test_netting_and_settle()
    test_boundaries()
    test_concurrency()

    # show a balance summary
    mgr = fresh()
    mgr.add_expense(Expense("e1", "Dinner", 90.0, "alice", SplitType.EQUAL,
                            [Split("alice"), Split("bob"), Split("carol")]))
    print("\nAlice's balances:", mgr.balances_for("alice"))
    print("Bob's balances:  ", mgr.balances_for("bob"))
    print("All assertions passed.")


if __name__ == "__main__":
    main()
