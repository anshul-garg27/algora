from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


class VehicleType(Enum):
    """Enum for vehicle types."""
    MOTORCYCLE = "motorcycle"
    CAR = "car"
    TRUCK = "truck"


class SpotSize(Enum):
    """Enum for parking spot sizes."""
    COMPACT = "compact"      # Fits: motorcycle, some cars
    REGULAR = "regular"      # Fits: car, truck (but not ideally)
    LARGE = "large"          # Fits: truck, car, motorcycle


# Mapping: vehicle type -> required spot size (minimum)
VEHICLE_TO_SPOT_SIZE = {
    VehicleType.MOTORCYCLE: SpotSize.COMPACT,
    VehicleType.CAR: SpotSize.REGULAR,
    VehicleType.TRUCK: SpotSize.LARGE,
}


@dataclass
class Vehicle:
    """Represents a vehicle entering the lot."""
    id: str
    license_plate: str
    vehicle_type: VehicleType

    @property
    def required_size(self) -> SpotSize:
        """Return the minimum spot size needed for this vehicle."""
        return VEHICLE_TO_SPOT_SIZE[self.vehicle_type]


@dataclass
class Ticket:
    """Represents a parking ticket (entry/exit record)."""
    ticket_id: str
    vehicle: Vehicle
    spot_id: str          # The spot this vehicle parked in
    level_number: int
    entry_time: datetime
    exit_time: Optional[datetime] = None
    fee: Optional[float] = None

    def is_active(self) -> bool:
        """Check if the vehicle is still parked."""
        return self.exit_time is None
