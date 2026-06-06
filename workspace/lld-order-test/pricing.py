from abc import ABC, abstractmethod
from datetime import datetime
import math


class PricingStrategy(ABC):
    """Abstract base class for pricing strategies."""

    @abstractmethod
    def calculate_fee(self, entry_time: datetime, exit_time: datetime) -> float:
        """Calculate the parking fee given entry and exit times (in hours)."""
        pass


class HourlyPricingStrategy(PricingStrategy):
    """Hourly pricing: charged per hour (rounded up)."""

    def __init__(self, rate_per_hour: float):
        self.rate_per_hour = rate_per_hour

    def calculate_fee(self, entry_time: datetime, exit_time: datetime) -> float:
        """
        Calculate fee: duration in hours × rate.
        Duration is rounded up to the nearest hour (minimum 1 hour).
        """
        duration_seconds = (exit_time - entry_time).total_seconds()
        duration_hours = duration_seconds / 3600.0
        # Round up to nearest hour (minimum 1 hour)
        hours_charged = max(1, math.ceil(duration_hours))
        return hours_charged * self.rate_per_hour


class FlatRatePricingStrategy(PricingStrategy):
    """Flat rate: fixed price regardless of duration."""

    def __init__(self, flat_rate: float):
        self.flat_rate = flat_rate

    def calculate_fee(self, entry_time: datetime, exit_time: datetime) -> float:
        """Always return the flat rate."""
        return self.flat_rate
