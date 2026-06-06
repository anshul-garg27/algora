"""ParkingLot facade — orchestrates enter/exit, owns the active-ticket registry."""
from __future__ import annotations
import threading
from models import Vehicle, ParkingFloor, Ticket
from strategies import (SpotAssignmentStrategy, PricingStrategy, NearestFirstStrategy,
                        HourlyPricing, Payment, PaymentMethod)


class LotFullError(Exception):
    pass


class ParkingLot:
    def __init__(self, floors: list[ParkingFloor],
                 assigner: SpotAssignmentStrategy | None = None,
                 pricer: PricingStrategy | None = None):
        self.floors = floors
        self.assigner = assigner or NearestFirstStrategy()
        self.pricer = pricer or HourlyPricing()
        self._active: dict[str, Ticket] = {}        # source of truth for in-flight cars
        self._lock = threading.RLock()              # one model: lock-guarded shared state

    def enter(self, vehicle: Vehicle, now: float) -> Ticket:
        if vehicle is None:
            raise ValueError("vehicle required")
        # select-and-assign must be atomic so two gates can't grab the same spot.
        with self._lock:
            found = self.assigner.find(self.floors, vehicle)
            if found is None:
                raise LotFullError(f"no spot for {vehicle}")
            spot, level = found
            spot.assign(vehicle)                    # commit while still holding the lock
            ticket = Ticket(vehicle, spot, level, now)
            self._active[ticket.id] = ticket
            return ticket

    def exit(self, ticket_id: str, method: PaymentMethod, now: float) -> Payment:
        with self._lock:
            ticket = self._active.get(ticket_id)
            if ticket is None:
                raise KeyError(f"unknown/used ticket {ticket_id}")
            amount = self.pricer.price(ticket, now)
            payment = Payment(amount)
            if not payment.pay(method):
                raise RuntimeError("payment failed")
            ticket.spot.release()                   # free spot only after payment ok
            del self._active[ticket_id]
            return payment

    def availability(self) -> dict[int, dict[str, int]]:
        with self._lock:
            return {f.level: f.counts() for f in self.floors}

    def active_count(self) -> int:
        with self._lock:
            return len(self._active)
