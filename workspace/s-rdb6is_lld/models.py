"""Domain entities, enums, and exceptions for the Splitwise LLD."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class SplitType(Enum):
    """How an expense's total is divided among participants."""
    EQUAL = "EQUAL"
    EXACT = "EXACT"
    PERCENT = "PERCENT"


# --- Specific error types (never a bare Exception) ---------------------------
class SplitwiseError(Exception):
    """Base class for all domain errors."""


class UnknownUserError(SplitwiseError):
    """A referenced user id is not registered."""


class InvalidExpenseError(SplitwiseError):
    """Expense amount/participants/values are invalid or inconsistent."""


class InvalidSplitError(SplitwiseError):
    """Split values do not reconcile to the expense total."""


class DuplicateError(SplitwiseError):
    """An id collides with an existing entity."""


@dataclass(frozen=True)
class User:
    """An immutable participant identity (safe to share across threads)."""
    user_id: str
    name: str
    email: str


@dataclass(frozen=True)
class Split:
    """One participant's owed share of an expense (a value object)."""
    user: User
    amount: Decimal


@dataclass(frozen=True)
class Expense:
    """Immutable record of a payment and how it splits across participants."""
    expense_id: str
    description: str
    amount: Decimal
    paid_by: User
    splits: tuple[Split, ...]
    split_type: SplitType
