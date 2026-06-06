"""The orchestrator/ledger: validates input, applies expenses, owns balances."""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Dict, List, Optional, Sequence

from models import (
    DuplicateExpenseError,
    Expense,
    InvalidAmountError,
    Split,
    SplitType,
    User,
    UserNotFoundError,
    to_cents,
)
from strategies import SplitStrategyFactory


class ExpenseManager:
    """Single source of truth for users, expenses, and pairwise balances.

    balance[a][b] = cents that `a` owes `b` (positive) and is always the exact
    negative of balance[b][a].
    """

    def __init__(self) -> None:
        self._users: Dict[str, User] = {}
        self._expenses: Dict[str, Expense] = {}
        self._balance: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    # --- registration ---
    def add_user(self, user: User) -> None:
        self._users[user.id] = user

    def _require_user(self, user_id: str) -> None:
        if user_id not in self._users:
            raise UserNotFoundError(f"unknown user {user_id}")

    # --- core: add an expense ---
    def add_expense(
        self,
        expense_id: str,
        description: str,
        amount: float,
        paid_by: str,
        split_type: SplitType,
        participants: Sequence[str],
        values: Optional[Sequence[float]] = None,
    ) -> Expense:
        # 1. Validate at the boundary BEFORE mutating any state.
        if expense_id in self._expenses:
            raise DuplicateExpenseError(f"expense {expense_id} already exists")
        amount_cents = to_cents(amount)
        if amount_cents <= 0:
            raise InvalidAmountError("amount must be positive")
        if not participants:
            raise InvalidAmountError("need at least one participant")
        if len(set(participants)) != len(participants):
            raise InvalidAmountError("duplicate participant in expense")
        self._require_user(paid_by)
        for uid in participants:
            self._require_user(uid)

        # 2. Compute shares via the chosen strategy (may raise InvalidSplitError).
        strategy = SplitStrategyFactory.get_strategy(split_type)
        splits: List[Split] = strategy.compute(amount_cents, participants, values)

        # 3. Apply to the ledger: each participant owes the payer their share.
        for split in splits:
            if split.user_id == paid_by:
                continue
            self._add_debt(debtor=split.user_id, creditor=paid_by, cents=split.amount_cents)

        expense = Expense(
            id=expense_id,
            description=description,
            amount_cents=amount_cents,
            paid_by=paid_by,
            splits=tuple(splits),
            created_at=time.time(),
        )
        self._expenses[expense_id] = expense
        return expense

    def _add_debt(self, debtor: str, creditor: str, cents: int) -> None:
        """Record that `debtor` owes `creditor` `cents`, keeping the ledger antisymmetric."""
        self._balance[debtor][creditor] += cents
        self._balance[creditor][debtor] -= cents

    # --- settlement ---
    def settle(self, payer: str, payee: str, amount: float) -> None:
        """`payer` pays `payee` -> reduces what payer owes payee."""
        self._require_user(payer)
        self._require_user(payee)
        cents = to_cents(amount)
        if cents <= 0:
            raise InvalidAmountError("settlement must be positive")
        # payer paying payee is the opposite of payer owing payee.
        self._add_debt(debtor=payee, creditor=payer, cents=cents)

    # --- queries ---
    def get_balance(self, a: str, b: str) -> int:
        """Net cents that `a` owes `b` (negative means `b` owes `a`)."""
        return self._balance[a][b]

    def get_balances(self, user_id: str) -> Dict[str, int]:
        """Net position of `user_id` vs each counterparty (positive = user owes)."""
        self._require_user(user_id)
        return {
            other: net
            for other, net in self._balance[user_id].items()
            if net != 0
        }
