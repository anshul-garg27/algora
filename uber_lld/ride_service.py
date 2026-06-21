"""RideService — the orchestrator. Owns all trips/drivers/riders and drives the
trip lifecycle. The clean version below has ZERO lock code; the thread-safe
subclass at the bottom overrides one method.
"""
from __future__ import annotations

import itertools
import threading
from contextlib import contextmanager
from typing import Iterator, Optional

from models import (
    Driver, DriverStatus, InvalidTripState, Location, Rider, RiderOnActiveTrip,
    Trip, TripStatus, UnknownEntity, VehicleType,
)
from payments import PaymentService
from strategies import DriverLocationIndex, MatchingStrategy, PricingStrategy


# ── OBSERVER seam: notifications decoupled from booking logic ────────────────
class TripObserver:
    def on_event(self, trip: Trip, event: str) -> None:  # pragma: no cover - base
        ...


# ── ORCHESTRATOR ─────────────────────────────────────────────────────────────
# ── WHY THIS CLASS ───────────────────────────────────────────────────────────
# Every operation flows through here. It holds the registry of in-flight trips
# (the orchestrator owns the truth) and coordinates the injected strategies.
# 🎙️ "RideService is the brain. Notice it depends only on interfaces — pricing,
#      matching, index, payment — all injected. It never builds a concrete."
class RideService:
    def __init__(
        self,
        matching: MatchingStrategy,
        pricing: PricingStrategy,
        index: DriverLocationIndex,
        payments: PaymentService,
    ) -> None:
        self._matching = matching
        self._pricing = pricing
        self._index = index
        self._payments = payments
        self._trips: dict[str, Trip] = {}
        self._drivers: dict[str, Driver] = {}
        self._riders: dict[str, Rider] = {}
        self._active_by_rider: dict[str, str] = {}  # rider_id -> active trip_id
        self._observers: list[TripObserver] = []
        self._counter = itertools.count(1)

    # ── registration / setup ────────────────────────────────────────────────
    def register_rider(self, rider: Rider) -> None:
        self._riders[rider.id] = rider

    def register_driver(self, driver: Driver) -> None:
        self._drivers[driver.id] = driver
        self._index.register(driver)

    def add_observer(self, obs: TripObserver) -> None:
        self._observers.append(obs)

    def update_driver_location(self, driver_id: str, loc: Location) -> None:
        driver = self._drivers.get(driver_id)
        if driver is None:
            raise UnknownEntity(f"unknown driver {driver_id}")
        driver.location = loc

    def get_trip(self, trip_id: str) -> Trip:
        trip = self._trips.get(trip_id)
        if trip is None:
            raise UnknownEntity(f"unknown trip {trip_id}")
        return trip

    # ── the no-op lock hook (Template Method) ────────────────────────────────
    # WHY: does nothing in the clean version — no lock code in this class at all.
    #      The thread-safe subclass overrides ONLY this method.
    @contextmanager
    def _lock(self, driver: Driver) -> Iterator[None]:
        yield

    def _emit(self, trip: Trip, event: str) -> None:
        for obs in self._observers:
            obs.on_event(trip, event)

    def _make_id(self, prefix: str) -> str:
        return f"{prefix}-{next(self._counter)}"

    # ── REQUEST RIDE: the interesting method ─────────────────────────────────
    def request_ride(
        self, rider_id: str, pickup: Location, drop: Location, vtype: VehicleType
    ) -> Trip:
        # 1-2. guards at the boundary
        if rider_id not in self._riders:
            raise UnknownEntity(f"unknown rider {rider_id}")
        if rider_id in self._active_by_rider:
            raise RiderOnActiveTrip(f"rider {rider_id} already on trip {self._active_by_rider[rider_id]}")

        # 3-5. price + create the trip (defined object before we even look for a driver)
        fare = self._pricing.estimate(pickup, drop, vtype)
        trip = Trip(
            id=self._make_id("trip"),
            rider_id=rider_id,
            pickup=pickup,
            drop=drop,
            vehicle_type=vtype,
            fare=fare,
        )
        self._trips[trip.id] = trip
        self._active_by_rider[rider_id] = trip.id

        # 6-9. find candidates, then atomically reserve the first one we can.
        candidates = self._index.nearest_available(pickup, vtype, k=5)
        ranked = self._matching.rank(candidates, pickup)
        chosen: Optional[Driver] = None
        for d in ranked:
            with self._lock(d):
                # WHY: check-and-reserve must be ONE atomic step. Two riders
                #      racing for the same driver: only one passes this gate,
                #      the other sees OFFERED/ON_TRIP and moves on.
                if d.status == DriverStatus.AVAILABLE:
                    d.mark_offered()
                    chosen = d
                    break

        # 10. no driver -> defined outcome, rider freed, request never lost
        if chosen is None:
            trip.mark_no_drivers()
            self._active_by_rider.pop(rider_id, None)
            self._emit(trip, "NO_DRIVERS")
            return trip

        # 11-12. commit the assignment
        trip.assign(chosen.id)
        chosen.current_trip_id = trip.id
        self._emit(trip, "DRIVER_ASSIGNED")
        return trip

    # ── lifecycle transitions ────────────────────────────────────────────────
    def accept_ride(self, trip_id: str, driver_id: str) -> Trip:
        trip = self.get_trip(trip_id)
        if trip.driver_id != driver_id:
            raise InvalidTripState(f"driver {driver_id} was not offered trip {trip_id}")
        driver = self._drivers[driver_id]
        trip.accept()                 # DRIVER_ASSIGNED -> EN_ROUTE
        driver.start_trip(trip_id)    # OFFERED -> ON_TRIP
        self._emit(trip, "EN_ROUTE")
        return trip

    def start_trip(self, trip_id: str) -> Trip:
        trip = self.get_trip(trip_id)
        trip.start()                  # EN_ROUTE -> IN_PROGRESS
        self._emit(trip, "IN_PROGRESS")
        return trip

    def complete_trip(self, trip_id: str) -> Trip:
        trip = self.get_trip(trip_id)
        if trip.status != TripStatus.IN_PROGRESS:
            raise InvalidTripState(f"trip {trip_id} not in progress ({trip.status.value})")
        # WHY: charge BEFORE transitioning. If payment raises, trip stays
        #      IN_PROGRESS and can be retried — outcome is defined, never lost.
        payment = self._payments.charge_for_trip(trip_id, trip.fare.total, trip.fare.currency)
        trip.complete(payment.id)
        self._drivers[trip.driver_id].end_trip()  # driver re-enters matching
        self._active_by_rider.pop(trip.rider_id, None)
        self._emit(trip, "COMPLETED")
        return trip

    def cancel_trip(self, trip_id: str) -> Trip:
        trip = self.get_trip(trip_id)
        trip.cancel()
        if trip.driver_id:
            self._drivers[trip.driver_id].release()  # idempotent free
        self._active_by_rider.pop(trip.rider_id, None)
        self._emit(trip, "CANCELLED")
        return trip


# ── THREAD-SAFE VERSION: overrides ONLY the _lock hook ───────────────────────
# 🎙️ "The thread-safe service is a subclass. The only change is this one method.
#      Per-driver lock so different drivers reserve in parallel; a map lock so
#      two threads creating the same driver's lock don't corrupt the dict."
class ThreadSafeRideService(RideService):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._locks: dict[str, threading.RLock] = {}
        self._map_lock = threading.Lock()

    @contextmanager
    def _lock(self, driver: Driver) -> Iterator[None]:
        with self._map_lock:                     # 1. lock the dict of locks
            lk = self._locks.setdefault(driver.id, threading.RLock())
        with lk:                                 # 2. lock this driver
            yield
