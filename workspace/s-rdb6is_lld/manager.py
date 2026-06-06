"""BalanceSheet (source of truth) + ExpenseManager (thread-safe facade)."""
from __future__ import annotations

import itertools
import threading
from collections import defaultdict
from decimal import Decimal

from models import (
    DuplicateError,
    Expense,
    InvalidExpenseError,
    SplitType,
    UnknownUserError,
    User,
)
from strategies import SplitStrategyFactory


class BalanceSheet:
    """Pairwise net debt. balances[A][B] = net amount B owes A.

    Invariant maintained on every mutation: balances[A][B] == -balances[B][A].
    """

    def __init__(self) -> None:
        self._balances: dict[str, dict[str, Decimal]] = defaultdict(
            lambda: defaultdict(lambda: Decimal("0"))
        )

    def _adjust(self, creditor: str, debtor: str, delta: Decimal) -> None:
        self._balances[creditor][debtor] += delta
        self._balances[debtor][creditor] -= delta

    def apply_expense(self, expense: Expense) -> None:
        payer = expense.paid_by.user_id
        for split in expense.splits:
            ower = split.user.user_id
            if ower == payer:
                continue  # payer's own share creates no debt
            # ower owes payer split.amount -> payer is creditor.
            self._adjust(payer, ower, split.amount)

    def settle(self, payer_id: str, payee_id: str, amount: Decimal) -> None:
        # payer pays payee back: reduces what payer owes payee.
        self._adjust(payer_id, payee_id, amount)

    def balances_of(self, user_id: str) -> dict[str, Decimal]:
        # Positive => the other user owes `user_id`; negative => user_id owes them.
        return {
            other: amt
            for other, amt in self._balances[user_id].items()
            if amt != Decimal("0")
        }


class ExpenseManager:
    """Facade orchestrating users, expenses, strategies, and balances.

    All shared mutable state (_users, _expenses, _sheet) is guarded by a single
    reentrant lock so check-then-act sequences are atomic.
    """

    def __init__(self) -> None:
        self._users: dict[str, User] = {}
        self._expenses: dict[str, Expense] = {}
        self._sheet = BalanceSheet()
        self._factory = SplitStrategyFactory()
        self._lock = threading.RLock()  # reentrant: guarded methods call helpers

    # --- registry --------------------------------------------------------
    def add_user(self, user: User) -> None:
        with self._lock:
            if user.user_id in self._users:
                raise DuplicateError(f"user {user.user_id} already exists")
            self._users[user.user_id] = user

    def _require_user(self, user_id: str) -> User:
        user = self._users.get(user_id)
        if user is None:
            raise UnknownUserError(f"unknown user {user_id}")
        return user

    # --- core operations -------------------------------------------------
    def add_expense(
        self,
        expense_id: str,
        description: str,
        amount: Decimal,
        paid_by_id: str,
        participant_ids: list[str],
        split_type: SplitType,
        values: list[Decimal] | None = None,
    ) -> Expense:
        with self._lock:  # validate + mutate atomically
            if amount <= Decimal("0"):
                raise InvalidExpenseError("amount must be positive")
            if expense_id in self._expenses:
                raise DuplicateError(f"expense {expense_id} already exists")
            if not participant_ids:
                raise InvalidExpenseError("need at least one participant")

            payer = self._require_user(paid_by_id)
            participants = [self._require_user(pid) for pid in participant_ids]

            strategy = self._factory.get(split_type)
            splits = strategy.compute(amount, participants, values)

            expense = Expense(
                expense_id=expense_id,
                description=description,
                amount=amount,
                paid_by=payer,
                splits=tuple(splits),
                split_type=split_type,
            )
            self._sheet.apply_expense(expense)
            self._expenses[expense_id] = expense
            return expense

    def settle_up(self, payer_id: str, payee_id: str, amount: Decimal) -> None:
        with self._lock:
            if amount <= Decimal("0"):
                raise InvalidExpenseError("settlement must be positive")
            self._require_user(payer_id)
            self._require_user(payee_id)
            self._sheet.settle(payer_id, payee_id, amount)

    def get_balances(self, user_id: str) -> dict[str, Decimal]:
        with self._lock:  # reads also lock: never observe a half-applied expense
            self._require_user(user_id)
            return self._sheet.balances_of(user_id)

    def simplify_group(self, user_ids: list[str]) -> list[tuple[str, str, Decimal]]:
        """Greedy debt simplification: minimal transfers to settle a group."""
        with self._lock:
            net: dict[str, Decimal] = {u: Decimal("0") for u in user_ids}
            for a, b in itertools.combinations(user_ids, 2):
                owed = self._sheet._balances[a][b]  # b owes a
                net[a] += owed
                net[b] -= owed
            creditors = [(u, v) for u, v in net.items() if v > 0]
            debtors = [(u, -v) for u, v in net.items() if v < 0]
            txns: list[tuple[str, str, Decimal]] = []
            i = j = 0
            while i < len(debtors) and j < len(creditors):
                d_user, d_amt = debtors[i]
                c_user, c_amt = creditors[j]
                pay = min(d_amt, c_amt)
                txns.append((d_user, c_user, pay))  # d_user pays c_user
                d_amt -= pay
                c_amt -= pay
                debtors[i] = (d_user, d_amt)
                creditors[j] = (c_user, c_amt)
                if d_amt == 0:
                    i += 1
                if c_amt == 0:
                    j += 1
            return txns
