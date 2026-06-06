"""Domain entities and enums for the parking lot."""
from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum
import threading
import itertools


class VehicleType(Enum):
    MOTORCYCLE = 1
    CAR = 2
    TRUCK = 3


class SpotType(Enum):
    SMALL = 1
    MEDIUM = 2
    LARGE = 3


# A vehicle of size T can use any spot whose size >= its own (fit-up).
FIT_UP = {
    VehicleType.MOTORCYCLE: [SpotType.SMALL, SpotType.MEDIUM, SpotType.LARGE],
    VehicleType.CAR: [SpotType.MEDIUM, SpotType.LARGE],
    VehicleType.TRUCK: [SpotType.LARGE],
}


class Vehicle(ABC):
    def __init__(self, plate: str, vtype: VehicleType):
        if not plate:
            raise ValueError("plate required")
        self.plate = plate
        self.type = vtype

    def __repr__(self):
        return f"{self.type.name}({self.plate})"


class Motorcycle(Vehicle):
    def __init__(self, plate): super().__init__(plate, VehicleType.MOTORCYCLE)


class Car(Vehicle):
    def __init__(self, plate): super().__init__(plate, VehicleType.CAR)


class Truck(Vehicle):
    def __init__(self, plate): super().__init__(plate, VehicleType.TRUCK)


class VehicleFactory:
    """Factory Method: build the right Vehicle subclass from a type."""
    _ctors = {VehicleType.MOTORCYCLE: Motorcycle,
              VehicleType.CAR: Car,
              VehicleType.TRUCK: Truck}

    @classmethod
    def create(cls, vtype: VehicleType, plate: str) -> Vehicle:
        if vtype not in cls._ctors:
            raise ValueError(f"unknown vehicle type {vtype}")
        return cls._ctors[vtype](plate)


class ParkingSpot:
    def __init__(self, spot_id: str, stype: SpotType):
        self.id = spot_id
        self.type = stype
        self.vehicle: Vehicle | None = None

    def is_free(self) -> bool:
        return self.vehicle is None

    def assign(self, v: Vehicle):
        if self.vehicle is not None:
            raise RuntimeError(f"spot {self.id} already occupied")
        self.vehicle = v

    def release(self):
        self.vehicle = None

    def __repr__(self):
        return f"Spot[{self.id},{self.type.name},{'free' if self.is_free() else 'busy'}]"


class ParkingFloor:
    """Owns spots; indexes them by SpotType for fast free-spot lookup."""
    def __init__(self, level: int):
        self.level = level
        self._by_type: dict[SpotType, list[ParkingSpot]] = {t: [] for t in SpotType}

    def add_spot(self, spot: ParkingSpot):
        self._by_type[spot.type].append(spot)

    def free_spots(self, stype: SpotType) -> list[ParkingSpot]:
        return [s for s in self._by_type[stype] if s.is_free()]

    def counts(self) -> dict[str, int]:
        return {t.name: len(self.free_spots(t)) for t in SpotType}


_ticket_seq = itertools.count(1)


class Ticket:
    """The in-flight record binding a vehicle to a spot — survives entry to exit."""
    def __init__(self, vehicle: Vehicle, spot: ParkingSpot, floor: int, entry_ts: float):
        self.id = f"T{next(_ticket_seq)}"
        self.vehicle = vehicle
        self.spot = spot
        self.floor = floor
        self.entry_ts = entry_ts

    def __repr__(self):
        return f"Ticket[{self.id},{self.vehicle},spot={self.spot.id}]"
