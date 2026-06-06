"""Split strategies (Strategy pattern) + a factory to resolve them."""
from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal, ROUND_HALF_UP

from models import (
    InvalidSplitError,
    Split,
    SplitType,
    User,
)

CENT = Decimal("0.01")


def _round(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


class SplitStrategy(ABC):
    """Contract: turn a total + participants (+ optional values) into Splits.

    Implementations MUST guarantee sum(split.amount) == amount exactly.
    """

    @abstractmethod
    def compute(
        self,
        amount: Decimal,
        participants: list[User],
        values: list[Decimal] | None,
    ) -> list[Split]:
        ...


class EqualSplitStrategy(SplitStrategy):
    """Divide equally; distribute leftover cents deterministically."""

    def compute(self, amount, participants, values=None) -> list[Split]:
        n = len(participants)
        if n == 0:
            raise InvalidSplitError("equal split needs at least one participant")
        base = _round(amount / n)
        splits = [Split(u, base) for u in participants]
        # Fix rounding drift on the first participant so shares sum to total.
        drift = amount - base * n
        if drift != Decimal("0"):
            first = splits[0]
            splits[0] = Split(first.user, _round(first.amount + drift))
        return splits


class ExactSplitStrategy(SplitStrategy):
    """Each participant owes an explicitly supplied amount; must sum to total."""

    def compute(self, amount, participants, values=None) -> list[Split]:
        if values is None or len(values) != len(participants):
            raise InvalidSplitError("exact split needs one value per participant")
        total = sum(values, Decimal("0"))
        if _round(total) != _round(amount):
            raise InvalidSplitError(
                f"exact amounts {total} do not sum to total {amount}"
            )
        return [Split(u, _round(v)) for u, v in zip(participants, values)]


class PercentSplitStrategy(SplitStrategy):
    """Each participant owes a percentage; percentages must sum to 100."""

    def compute(self, amount, participants, values=None) -> list[Split]:
        if values is None or len(values) != len(participants):
            raise InvalidSplitError("percent split needs one percent per participant")
        total_pct = sum(values, Decimal("0"))
        if _round(total_pct) != Decimal("100.00"):
            raise InvalidSplitError(f"percentages sum to {total_pct}, not 100")
        splits = [Split(u, _round(amount * p / Decimal("100"))) for u, p in
                  zip(participants, values)]
        drift = amount - sum((s.amount for s in splits), Decimal("0"))
        if drift != Decimal("0"):
            first = splits[0]
            splits[0] = Split(first.user, _round(first.amount + drift))
        return splits


class SplitStrategyFactory:
    """Resolve a SplitType to its (stateless, shareable) strategy instance."""

    def __init__(self) -> None:
        self._registry: dict[SplitType, SplitStrategy] = {
            SplitType.EQUAL: EqualSplitStrategy(),
            SplitType.EXACT: ExactSplitStrategy(),
            SplitType.PERCENT: PercentSplitStrategy(),
        }

    def get(self, split_type: SplitType) -> SplitStrategy:
        try:
            return self._registry[split_type]
        except KeyError as exc:
            raise InvalidSplitError(f"no strategy for {split_type}") from exc
