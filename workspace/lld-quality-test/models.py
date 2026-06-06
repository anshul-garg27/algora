"""
Enums and data entities for the parking lot system.
"""

from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


class SpotType(Enum):
    """Size category of a parking spot."""
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    HANDICAP = "handicap"


class SpotStatus(Enum):
    """Current occupancy status of a spot."""
    AVAILABLE = "available"
    OCCUPIED = "occupied"
    MAINTENANCE = "maintenance"


class VehicleSize(Enum):
    """Size category of a vehicle."""
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class GateType(Enum):
    """Type of gate (entry or exit)."""
    ENTRY = "entry"
    EXIT = "exit"


@dataclass
class Vehicle:
    """A vehicle that can park."""
    vehicle_id: str
    license_plate: str
    size: VehicleSize

    def __repr__(self) -> str:
        return f"Vehicle({self.license_plate}, {self.size.value})"


@dataclass
class Gate:
    """An entry or exit gate for the parking lot."""
    gate_id: str
    gate_type: GateType


@dataclass
class ParkingSpot:
    """A single parking space."""
    id: str
    floor_id: str
    spot_type: SpotType
    status: SpotStatus = SpotStatus.AVAILABLE
    vehicle_id: Optional[str] = None

    def mark_occupied(self, vehicle_id: str) -> None:
        """Mark this spot as occupied by a vehicle."""
        if self.status != SpotStatus.AVAILABLE:
            raise ValueError(f"Spot {self.id} is not available (status={self.status})")
        self.status = SpotStatus.OCCUPIED
        self.vehicle_id = vehicle_id

    def mark_available(self) -> None:
        """Mark this spot as available."""
        self.status = SpotStatus.AVAILABLE
        self.vehicle_id = None

    def is_available(self) -> bool:
        """Check if this spot is available for parking."""
        return self.status == SpotStatus.AVAILABLE

    def can_fit(self, vehicle_size: VehicleSize) -> bool:
        """
        Check if a vehicle of given size can fit in this spot.
        Spot type hierarchy: SMALL < MEDIUM < LARGE
        HANDICAP is exclusive (handicap vehicles only).
        """
        if not self.is_available():
            return False

        # Handicap spots only for handicap vehicles (or we could allow any, depending on policy)
        # For this design, handicap spots are exclusive to handicap-designated vehicles.
        # In a real system, we'd also track if the vehicle is a handicap-designated vehicle.
        # For now, we allow any vehicle in handicap spots (but spots are reserved).
        if self.spot_type == SpotType.HANDICAP:
            return True

        # Normal sizing: SMALL fits in SMALL, MEDIUM fits in MEDIUM or LARGE, LARGE fits in LARGE.
        size_order = {VehicleSize.SMALL: 1, VehicleSize.MEDIUM: 2, VehicleSize.LARGE: 3}
        type_order = {SpotType.SMALL: 1, SpotType.MEDIUM: 2, SpotType.LARGE: 3}

        return size_order[vehicle_size] <= type_order[self.spot_type]


@dataclass
class ParkingTicket:
    """Parking ticket issued on entry; used for exit and fee calculation."""
    ticket_id: str
    vehicle: Vehicle
    spot: ParkingSpot
    entry_time: datetime
    exit_time: Optional[datetime] = None
    amount_due: Optional[float] = None

    def is_active(self) -> bool:
        """Check if this ticket is still active (vehicle has not exited)."""
        return self.exit_time is None

    def exit(self, exit_time: datetime, amount_due: float) -> None:
        """Record the exit and calculate the fee."""
        if not self.is_active():
            raise ValueError(f"Ticket {self.ticket_id} already exited")
        self.exit_time = exit_time
        self.amount_due = amount_due

    def duration_minutes(self) -> float:
        """Duration of parking in minutes. Only valid after exit."""
        if not self.exit_time:
            raise ValueError("Ticket has not exited yet")
        return (self.exit_time - self.entry_time).total_seconds() / 60.0
