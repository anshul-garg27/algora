"""ExpenseManager: the orchestrator that owns the truth (users, expenses,
balance ledger). Thread-safe via a single reentrant lock. Supports an Observer
seam for notifications."""
from __future__ import annotations
import threading
from collections import defaultdict
from typing import Dict, List, Optional, Protocol

from models import User, Expense, Split, SplitType, Group
from splits import SplitStrategyFactory, CENT


class ExpenseObserver(Protocol):
    def on_expense(self, expense: Expense) -> None: ...


class BalanceSheet:
    """Net pairwise balances. balance[a][b] > 0 means a is owed b's money,
    i.e. b owes a `balance[a][b]`. We keep it antisymmetric."""
    def __init__(self):
        self._bal: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))

    def transfer(self, debtor: str, creditor: str, amount: float) -> None:
        if debtor == creditor or amount == 0:
            return
        # debtor owes creditor `amount`
        self._bal[creditor][debtor] = round(self._bal[creditor][debtor] + amount, 2)
        self._bal[debtor][creditor] = round(self._bal[debtor][creditor] - amount, 2)

    def owes(self, debtor: str, creditor: str) -> float:
        """How much debtor owes creditor (negative => creditor owes debtor)."""
        return self._bal[creditor][debtor]

    def balances_for(self, user_id: str) -> Dict[str, float]:
        """Positive value => the other party owes `user_id`; negative => user owes them."""
        return {other: amt for other, amt in self._bal[user_id].items() if abs(amt) > CENT}


class ExpenseManager:
    def __init__(self):
        self._users: Dict[str, User] = {}
        self._groups: Dict[str, Group] = {}
        self._expenses: Dict[str, Expense] = {}
        self._sheet = BalanceSheet()
        self._observers: List[ExpenseObserver] = []
        self._lock = threading.RLock()

    # ---- registration ----
    def add_user(self, user: User) -> None:
        with self._lock:
            if user.user_id in self._users:
                raise ValueError(f"Duplicate user id {user.user_id}")
            self._users[user.user_id] = user

    def add_group(self, group: Group) -> None:
        with self._lock:
            for m in group.member_ids:
                self._require_user(m)
            self._groups[group.group_id] = group

    def register_observer(self, obs: ExpenseObserver) -> None:
        with self._lock:
            self._observers.append(obs)

    # ---- core use case ----
    def add_expense(self, expense: Expense) -> Expense:
        with self._lock:
            if expense.expense_id in self._expenses:
                raise ValueError(f"Duplicate expense id {expense.expense_id}")
            self._require_user(expense.paid_by)
            seen = set()
            for s in expense.splits:
                self._require_user(s.user_id)
                if s.user_id in seen:
                    raise ValueError(f"Duplicate participant {s.user_id} in expense")
                seen.add(s.user_id)

            # Strategy resolves & validates owed amounts (raises on bad input).
            strategy = SplitStrategyFactory.get(expense.split_type)
            strategy.resolve(expense.amount, expense.splits)

            # Commit to the ledger: each participant owes the payer their share.
            for s in expense.splits:
                if s.user_id != expense.paid_by:
                    self._sheet.transfer(debtor=s.user_id,
                                         creditor=expense.paid_by,
                                         amount=s.owed)

            self._expenses[expense.expense_id] = expense
            for obs in self._observers:
                obs.on_expense(expense)
            return expense

    def settle(self, payer: str, payee: str, amount: float) -> None:
        with self._lock:
            self._require_user(payer)
            self._require_user(payee)
            if amount <= 0:
                raise ValueError("Settlement amount must be positive")
            # payer pays payee -> reduces what payer owes payee
            self._sheet.transfer(debtor=payee, creditor=payer, amount=amount)

    # ---- queries ----
    def balances_for(self, user_id: str) -> Dict[str, float]:
        with self._lock:
            self._require_user(user_id)
            return self._sheet.balances_for(user_id)

    def owes(self, debtor: str, creditor: str) -> float:
        with self._lock:
            return self._sheet.owes(debtor, creditor)

    # ---- helpers ----
    def _require_user(self, user_id: str) -> None:
        if user_id not in self._users:
            raise ValueError(f"Unknown user id {user_id}")
