"""Strategy interfaces + concrete strategies for assignment, pricing, payment."""
from __future__ import annotations
from abc import ABC, abstractmethod
import math
from models import Vehicle, VehicleType, SpotType, ParkingFloor, ParkingSpot, Ticket, FIT_UP


class SpotAssignmentStrategy(ABC):
    @abstractmethod
    def find(self, floors: list[ParkingFloor], vehicle: Vehicle) -> tuple[ParkingSpot, int] | None:
        ...


class NearestFirstStrategy(SpotAssignmentStrategy):
    """Lowest floor first, smallest compatible spot first (fit-up aware)."""
    def find(self, floors, vehicle):
        for floor in sorted(floors, key=lambda f: f.level):
            for stype in FIT_UP[vehicle.type]:          # smallest fitting size first
                free = floor.free_spots(stype)
                if free:
                    return free[0], floor.level
        return None


class PricingStrategy(ABC):
    @abstractmethod
    def price(self, ticket: Ticket, exit_ts: float) -> float:
        ...


class HourlyPricing(PricingStrategy):
    RATE = {VehicleType.MOTORCYCLE: 10.0, VehicleType.CAR: 20.0, VehicleType.TRUCK: 40.0}

    def price(self, ticket, exit_ts):
        hours = max(1, math.ceil((exit_ts - ticket.entry_ts) / 3600.0))  # min 1 hr
        return hours * self.RATE[ticket.vehicle.type]


class PaymentMethod(ABC):
    @abstractmethod
    def collect(self, amount: float) -> bool:
        ...


class CashPayment(PaymentMethod):
    def collect(self, amount): return True


class CardPayment(PaymentMethod):
    def collect(self, amount): return amount >= 0  # pretend gateway always approves


class Payment:
    def __init__(self, amount: float):
        self.amount = amount
        self.paid = False

    def pay(self, method: PaymentMethod) -> bool:
        self.paid = method.collect(self.amount)
        return self.paid
