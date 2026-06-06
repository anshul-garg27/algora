"""Split strategies (Strategy pattern) + a factory to pick one.

Each strategy is responsible for VALIDATING its inputs and RESOLVING the
`owed` amount on every Split so the rest of the system works with one shape.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List

from models import Split, SplitType

CENT = 0.01  # tolerance for floating-point money comparisons


class SplitStrategy(ABC):
    @abstractmethod
    def resolve(self, total: float, splits: List[Split]) -> None:
        """Validate and fill `owed` on each split in place. Raise ValueError if invalid."""
        ...


class EqualSplit(SplitStrategy):
    def resolve(self, total: float, splits: List[Split]) -> None:
        n = len(splits)
        share = round(total / n, 2)
        # distribute remainder cents to the first participants so sum == total exactly
        allocated = 0.0
        for i, s in enumerate(splits):
            if i == n - 1:
                s.owed = round(total - allocated, 2)
            else:
                s.owed = share
                allocated = round(allocated + share, 2)


class ExactSplit(SplitStrategy):
    def resolve(self, total: float, splits: List[Split]) -> None:
        s = sum(sp.amount for sp in splits)
        if abs(s - total) > CENT:
            raise ValueError(f"Exact shares {s} must sum to total {total}")
        for sp in splits:
            if sp.amount < 0:
                raise ValueError("Exact share cannot be negative")
            sp.owed = round(sp.amount, 2)


class PercentSplit(SplitStrategy):
    def resolve(self, total: float, splits: List[Split]) -> None:
        p = sum(sp.percent for sp in splits)
        if abs(p - 100.0) > CENT:
            raise ValueError(f"Percentages {p} must sum to 100")
        allocated = 0.0
        for i, sp in enumerate(splits):
            if sp.percent < 0:
                raise ValueError("Percent cannot be negative")
            if i == len(splits) - 1:
                sp.owed = round(total - allocated, 2)
            else:
                sp.owed = round(total * sp.percent / 100.0, 2)
                allocated = round(allocated + sp.owed, 2)


class SplitStrategyFactory:
    _registry = {
        SplitType.EQUAL: EqualSplit(),
        SplitType.EXACT: ExactSplit(),
        SplitType.PERCENT: PercentSplit(),
    }

    @classmethod
    def get(cls, split_type: SplitType) -> SplitStrategy:
        strat = cls._registry.get(split_type)
        if strat is None:
            raise ValueError(f"Unknown split type {split_type}")
        return strat
