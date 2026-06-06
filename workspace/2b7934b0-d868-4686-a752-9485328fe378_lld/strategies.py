"""Split algorithms (Strategy pattern) and their factory."""
from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import List, Optional, Sequence

from models import InvalidSplitError, Split, SplitType, to_cents


def distribute_by_weights(total_cents: int, weights: Sequence[float]) -> List[int]:
    """Split total_cents proportionally to positive weights with NO penny lost.

    Floors each share, then hands the leftover cents to the largest fractional
    remainders. Guarantees sum(result) == total_cents exactly.
    """
    if any(w <= 0 for w in weights):
        raise InvalidSplitError("weights must be positive")
    total_w = sum(weights)
    raw = [total_cents * w / total_w for w in weights]
    floors = [int(math.floor(x)) for x in raw]
    remainder = total_cents - sum(floors)
    # Indices ordered by largest fractional part get +1 cent first.
    order = sorted(range(len(weights)), key=lambda i: raw[i] - floors[i], reverse=True)
    for i in range(remainder):
        floors[order[i]] += 1
    return floors


class SplitStrategy(ABC):
    """Interface: turn an amount + participants (+ optional inputs) into Splits."""

    @abstractmethod
    def compute(
        self,
        amount_cents: int,
        user_ids: Sequence[str],
        values: Optional[Sequence[float]] = None,
    ) -> List[Split]:
        ...


class EqualSplitStrategy(SplitStrategy):
    """Divide equally; leftover pennies distributed deterministically."""

    def compute(self, amount_cents, user_ids, values=None) -> List[Split]:
        if not user_ids:
            raise InvalidSplitError("need at least one participant")
        shares = distribute_by_weights(amount_cents, [1] * len(user_ids))
        return [Split(uid, c) for uid, c in zip(user_ids, shares)]


class ExactSplitStrategy(SplitStrategy):
    """Each participant owes an explicitly provided amount; must sum to total."""

    def compute(self, amount_cents, user_ids, values=None) -> List[Split]:
        if values is None or len(values) != len(user_ids):
            raise InvalidSplitError("exact split needs one amount per participant")
        cents = [to_cents(v) for v in values]
        if any(c < 0 for c in cents):
            raise InvalidSplitError("exact amounts must be non-negative")
        if sum(cents) != amount_cents:
            raise InvalidSplitError(
                f"exact splits sum to {sum(cents)} but total is {amount_cents}"
            )
        return [Split(uid, c) for uid, c in zip(user_ids, cents)]


class PercentSplitStrategy(SplitStrategy):
    """Each participant owes a percentage; percentages must sum to 100."""

    def compute(self, amount_cents, user_ids, values=None) -> List[Split]:
        if values is None or len(values) != len(user_ids):
            raise InvalidSplitError("percent split needs one percent per participant")
        if abs(sum(values) - 100.0) > 1e-6:
            raise InvalidSplitError(f"percentages sum to {sum(values)}, must be 100")
        shares = distribute_by_weights(amount_cents, list(values))
        return [Split(uid, c) for uid, c in zip(user_ids, shares)]


class SplitStrategyFactory:
    """Maps a SplitType to its (stateless, shared) strategy instance."""

    _STRATEGIES = {
        SplitType.EQUAL: EqualSplitStrategy(),
        SplitType.EXACT: ExactSplitStrategy(),
        SplitType.PERCENT: PercentSplitStrategy(),
    }

    @classmethod
    def get_strategy(cls, split_type: SplitType) -> SplitStrategy:
        if split_type not in cls._STRATEGIES:
            raise InvalidSplitError(f"unknown split type {split_type}")
        return cls._STRATEGIES[split_type]
