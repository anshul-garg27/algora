"""Parking lot core models and enums."""

from enum import Enum
from dataclasses import dataclass
from typing import Optional
import uuid


class VehicleSize(Enum):
    """Enum for vehicle and spot sizes."""
    COMPACT = 1
    NORMAL = 2
    LARGE = 3

    def fits_in(self, spot_size: "VehicleSize") -> bool:
        """Check if this vehicle size fits in a spot of given size."""
        return self.value <= spot_size.value


@dataclass
class Vehicle:
    """Represents a parked or arriving vehicle."""
    id: str
    size: VehicleSize
    license_plate: str

    @staticmethod
    def create(size: VehicleSize, license_plate: str) -> "Vehicle":
        return Vehicle(id=str(uuid.uuid4()), size=size, license_plate=license_plate)


class ParkingSpot:
    """A single parking spot on a floor."""

    def __init__(self, spot_id: int, size: VehicleSize, floor_id: int):
        self.id: int = spot_id
        self.size: VehicleSize = size
        self.floor_id: int = floor_id
        self.is_occupied: bool = False
        self.current_vehicle_id: Optional[str] = None

    def occupy(self, vehicle_id: str) -> None:
        """Mark this spot as occupied by a vehicle."""
        if self.is_occupied:
            raise ValueError(f"Spot {self.id} is already occupied")
        self.is_occupied = True
        self.current_vehicle_id = vehicle_id

    def vacate(self) -> Optional[str]:
        """Mark this spot as vacant and return the vehicle that was in it."""
        if not self.is_occupied:
            raise ValueError(f"Spot {self.id} is already vacant")
        vehicle_id = self.current_vehicle_id
        self.is_occupied = False
        self.current_vehicle_id = None
        return vehicle_id

    def __repr__(self) -> str:
        status = f"occupied by {self.current_vehicle_id}" if self.is_occupied else "vacant"
        return f"Spot({self.id}, size={self.size.name}, floor={self.floor_id}, {status})"


class ParkingFloor:
    """A floor in the parking lot, containing multiple spots."""

    def __init__(self, floor_id: int, spots: list[ParkingSpot]):
        self.id: int = floor_id
        self.spots: list[ParkingSpot] = spots

    def get_available_spots(self, vehicle_size: VehicleSize) -> list[ParkingSpot]:
        """Return all vacant spots that can fit the vehicle, ordered by spot size (smallest first)."""
        available = [
            spot for spot in self.spots
            if not spot.is_occupied and vehicle_size.fits_in(spot.size)
        ]
        # Sort by spot size (ascending) to assign smallest suitable spot first.
        return sorted(available, key=lambda s: s.size.value)

    def __repr__(self) -> str:
        occupied = sum(1 for s in self.spots if s.is_occupied)
        return f"Floor({self.id}, {occupied}/{len(self.spots)} occupied)"


@dataclass
class Ticket:
    """Parking ticket issued on entry, used on exit."""
    id: str
    vehicle_id: str
    spot_id: int
    entry_time: float
    exit_time: Optional[float] = None

    @staticmethod
    def create(vehicle_id: str, spot_id: int, entry_time: float) -> "Ticket":
        return Ticket(id=str(uuid.uuid4()), vehicle_id=vehicle_id, spot_id=spot_id, entry_time=entry_time)

    def duration_hours(self, exit_time: float) -> float:
        """Calculate duration in hours between entry and exit."""
        return (exit_time - self.entry_time) / 3600.0


class ParkingRate:
    """Calculates parking fees."""

    def __init__(self, hourly_rate: float):
        self.hourly_rate: float = hourly_rate

    def calculate_fee(self, duration_hours: float) -> float:
        """Calculate fee for a given duration. Minimum 1 hour."""
        if duration_hours < 0:
            raise ValueError("Duration cannot be negative")
        # Minimum 1 hour; round up for partial hours.
        billable_hours = max(1, int(duration_hours) + (1 if duration_hours % 1 > 0 else 0))
        return billable_hours * self.hourly_rate


# Custom Exceptions
class ParkingError(Exception):
    """Base exception for parking lot errors."""
    pass


class NoSpotAvailableError(ParkingError):
    """Raised when no suitable spot is available."""
    pass


class InvalidTicketError(ParkingError):
    """Raised when a ticket is invalid or not found."""
    pass


class SpotOccupiedError(ParkingError):
    """Raised when trying to occupy an already-occupied spot."""
    pass
