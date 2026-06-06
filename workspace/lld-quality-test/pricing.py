"""
Pricing strategies for parking fees.
"""

from abc import ABC, abstractmethod
from datetime import datetime
import math


class PricingStrategy(ABC):
    """Abstract base class for parking fee calculation."""

    @abstractmethod
    def calculate_fee(self, entry_time: datetime, exit_time: datetime) -> float:
        """
        Calculate the fee for a parking session.

        Args:
            entry_time: When the vehicle entered.
            exit_time: When the vehicle exited.

        Returns:
            The fee in currency units.
        """
        pass


class HourlyPricingStrategy(PricingStrategy):
    """Charges a fixed rate per hour, rounding up partial hours."""

    def __init__(self, hourly_rate: float) -> None:
        """
        Initialize with an hourly rate.

        Args:
            hourly_rate: The cost per hour (e.g., 5.0 for $5/hour).
        """
        if hourly_rate <= 0:
            raise ValueError("Hourly rate must be positive")
        self.hourly_rate = hourly_rate

    def calculate_fee(self, entry_time: datetime, exit_time: datetime) -> float:
        """
        Calculate fee: charge for each full or partial hour.

        Example: parked for 1h 15m → charged for 2 hours.
        """
        duration_minutes = (exit_time - entry_time).total_seconds() / 60.0
        if duration_minutes < 0:
            raise ValueError("Exit time cannot be before entry time")

        # Round up to the nearest hour
        hours = math.ceil(duration_minutes / 60.0)
        # Ensure at least 1 hour charged (even for very short stays)
        hours = max(1, hours)

        return hours * self.hourly_rate


class FlatRatePricingStrategy(PricingStrategy):
    """Charges a flat rate regardless of duration."""

    def __init__(self, flat_rate: float) -> None:
        """
        Initialize with a flat rate.

        Args:
            flat_rate: The fixed cost per parking session.
        """
        if flat_rate <= 0:
            raise ValueError("Flat rate must be positive")
        self.flat_rate = flat_rate

    def calculate_fee(self, entry_time: datetime, exit_time: datetime) -> float:
        """Return the flat rate."""
        return self.flat_rate
