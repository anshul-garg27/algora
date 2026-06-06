"""Core domain entities and enums for the Splitwise LLD."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List


class SplitType(Enum):
    EQUAL = "EQUAL"
    EXACT = "EXACT"
    PERCENT = "PERCENT"


@dataclass(frozen=True)
class User:
    user_id: str
    name: str
    email: str = ""


@dataclass
class Split:
    """One participant's owed portion of an expense. Always carries the user
    AND the resolved amount so no information is lost downstream."""
    user_id: str
    amount: float = 0.0          # used by EXACT
    percent: float = 0.0         # used by PERCENT
    owed: float = 0.0            # resolved amount this user owes (filled by strategy)


@dataclass
class Expense:
    expense_id: str
    description: str
    amount: float
    paid_by: str
    split_type: SplitType
    splits: List[Split]
    group_id: str = ""

    def __post_init__(self):
        if self.amount <= 0:
            raise ValueError(f"Expense amount must be positive, got {self.amount}")
        if not self.splits:
            raise ValueError("Expense must have at least one split")


@dataclass
class Group:
    group_id: str
    name: str
    member_ids: List[str] = field(default_factory=list)
