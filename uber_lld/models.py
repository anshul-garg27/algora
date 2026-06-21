"""Domain entities + enums + exceptions for the ride-hailing core.

Read this file top-to-bottom in the interview: enums first (the vocabulary),
then the immutable data holders, then the two state machines (Trip, Driver).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ── ENUMS: the vocabulary every other class speaks ───────────────────────────
# 🎙️ "I start with states because they define what's legal everywhere else."
class VehicleType(Enum):
    UBERX = "UberX"
    UBERXL = "UberXL"
    UBERBLACK = "UberBlack"


class DriverStatus(Enum):
    OFFLINE = "OFFLINE"      # not taking rides
    AVAILABLE = "AVAILABLE"  # can be matched
    OFFERED = "OFFERED"      # reserved for a trip, awaiting accept (the race-critical state)
    ON_TRIP = "ON_TRIP"      # actively driving a rider


class TripStatus(Enum):
    REQUESTED = "REQUESTED"
    DRIVER_ASSIGNED = "DRIVER_ASSIGNED"
    EN_ROUTE = "EN_ROUTE"          # driver heading to pickup
    IN_PROGRESS = "IN_PROGRESS"    # rider on board
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    NO_DRIVERS = "NO_DRIVERS"      # defined outcome when nobody is available


# ── EXCEPTIONS: specific types, never bare Exception ─────────────────────────
class RideError(Exception):
    """Base for everything this domain raises."""


class UnknownEntity(RideError):
    pass


class InvalidTripState(RideError):
    pass


class RiderOnActiveTrip(RideError):
    pass


class PaymentFailed(RideError):
    pass


# ── IMMUTABLE DATA HOLDERS (frozen = cannot change after creation) ───────────
@dataclass(frozen=True)
class Location:
    # WHY: frozen — a coordinate is a value; it never mutates in place.
    lat: float
    lng: float

    def distance_km(self, other: "Location") -> float:
        # WHY: haversine = real great-circle distance on a sphere, not flat math,
        #      so matching is correct over real lat/lng.
        R = 6371.0
        p1, p2 = math.radians(self.lat), math.radians(other.lat)
        dphi = math.radians(other.lat - self.lat)
        dl = math.radians(other.lng - self.lng)
        a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return 2 * R * math.asin(math.sqrt(a))


@dataclass(frozen=True)
class Vehicle:
    id: str
    type: VehicleType
    plate: str


@dataclass(frozen=True)
class Rider:
    id: str
    name: str


@dataclass(frozen=True)
class Fare:
    # WHY: frozen — the quote is fixed at request time so the rider is never
    #      re-priced mid-trip even if surge changes under them.
    base: float
    distance_cost: float
    surge: float
    total: float
    currency: str = "USD"


# ── DRIVER: a small state machine that makes reservation safe ────────────────
# ── WHY THIS CLASS ───────────────────────────────────────────────────────────
# A Driver owns its own availability. Reservation lives here so the orchestrator
# never sets a status it shouldn't.
# 🎙️ "Driver is a tiny state machine. The OFFERED state is the whole trick — it
#      lets us reserve a driver before the trip is fully assigned, so two riders
#      can't both grab them."
@dataclass
class Driver:
    id: str
    name: str
    vehicle: Vehicle
    location: Location
    status: DriverStatus = DriverStatus.AVAILABLE
    current_trip_id: Optional[str] = None

    def mark_offered(self) -> None:
        # WHY: only an AVAILABLE driver can be reserved. The caller checks this
        #      INSIDE a lock (see RideService.request_ride) so it's atomic.
        if self.status != DriverStatus.AVAILABLE:
            raise InvalidTripState(f"driver {self.id} not available ({self.status.value})")
        self.status = DriverStatus.OFFERED

    def start_trip(self, trip_id: str) -> None:
        self.status = DriverStatus.ON_TRIP
        self.current_trip_id = trip_id

    def end_trip(self) -> None:
        self.status = DriverStatus.AVAILABLE
        self.current_trip_id = None

    def release(self) -> None:
        # WHY: safe to call twice — second call does nothing harmful. Used by
        #      cancel and by a declined offer; whichever fires first wins.
        self.status = DriverStatus.AVAILABLE
        self.current_trip_id = None


# ── TRIP: the central state machine ──────────────────────────────────────────
# ── WHY THIS CLASS ───────────────────────────────────────────────────────────
# Trip owns the single source of truth for "what status can follow what".
# Without this, transition rules leak across the service as scattered ifs.
# 🎙️ "Trip is the heart. The allowed-transitions map means an illegal flow —
#      like starting before accepting — is impossible by construction."
_ALLOWED: dict[TripStatus, set[TripStatus]] = {
    TripStatus.REQUESTED: {TripStatus.DRIVER_ASSIGNED, TripStatus.NO_DRIVERS, TripStatus.CANCELLED},
    TripStatus.DRIVER_ASSIGNED: {TripStatus.EN_ROUTE, TripStatus.CANCELLED},
    TripStatus.EN_ROUTE: {TripStatus.IN_PROGRESS, TripStatus.CANCELLED},
    TripStatus.IN_PROGRESS: {TripStatus.COMPLETED},
    # terminal states have no outgoing edges
}


@dataclass
class Trip:
    id: str
    rider_id: str
    pickup: Location
    drop: Location
    vehicle_type: VehicleType
    fare: Fare
    status: TripStatus = TripStatus.REQUESTED
    driver_id: Optional[str] = None
    payment_id: Optional[str] = None

    def _transition(self, target: TripStatus) -> None:
        # WHY: one gate for every state change — the rule that must always be
        #      true (no illegal jumps) is enforced in exactly one place.
        if target not in _ALLOWED.get(self.status, set()):
            raise InvalidTripState(f"cannot go {self.status.value} -> {target.value}")
        self.status = target

    def assign(self, driver_id: str) -> None:
        self._transition(TripStatus.DRIVER_ASSIGNED)
        self.driver_id = driver_id

    def mark_no_drivers(self) -> None:
        self._transition(TripStatus.NO_DRIVERS)

    def accept(self) -> None:
        self._transition(TripStatus.EN_ROUTE)

    def start(self) -> None:
        self._transition(TripStatus.IN_PROGRESS)

    def complete(self, payment_id: str) -> None:
        self._transition(TripStatus.COMPLETED)
        self.payment_id = payment_id

    def cancel(self) -> None:
        self._transition(TripStatus.CANCELLED)
