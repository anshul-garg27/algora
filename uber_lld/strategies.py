"""The three Strategy seams: pricing, matching, and the geo index.

These are the parts Uber changes most often. The orchestrator depends only on
the abstract base classes here, so a new policy is a new subclass — zero core
changes (Open/Closed).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable

from models import Driver, DriverStatus, Fare, Location, VehicleType


# ── PRICING STRATEGY ─────────────────────────────────────────────────────────
# 🎙️ "Pricing is a strategy because surge, promos and per-city rates change
#      constantly. The service just asks for an estimate."
class PricingStrategy(ABC):
    @abstractmethod
    def estimate(self, pickup: Location, drop: Location, vtype: VehicleType) -> Fare:
        ...


@dataclass
class SurgePricingStrategy(PricingStrategy):
    # (base, per_km, per_min) per vehicle type
    RATES = {
        VehicleType.UBERX: (2.5, 1.2, 0.30),
        VehicleType.UBERXL: (3.5, 1.8, 0.40),
        VehicleType.UBERBLACK: (5.0, 2.5, 0.60),
    }
    MIN_FARE = 5.0
    KM_PER_MIN = 0.5  # assume ~30 km/h => 0.5 km per minute
    # WHY: surge is injected as a function of pickup location so demand/zone
    #      logic can be swapped or mocked in tests without touching pricing math.
    surge_fn: Callable[[Location], float] = lambda loc: 1.0

    def estimate(self, pickup: Location, drop: Location, vtype: VehicleType) -> Fare:
        base, per_km, per_min = self.RATES[vtype]
        dist = pickup.distance_km(drop)
        est_min = dist / self.KM_PER_MIN
        surge = self.surge_fn(pickup)
        distance_cost = round(per_km * dist + per_min * est_min, 2)
        raw = (base + distance_cost) * surge
        total = round(max(raw, self.MIN_FARE), 2)  # WHY: never charge below the floor
        return Fare(base=base, distance_cost=distance_cost, surge=surge, total=total)


# ── MATCHING STRATEGY ────────────────────────────────────────────────────────
# 🎙️ "Matching is a strategy too — nearest today, best-ETA or highest-rating
#      tomorrow. The orchestrator never knows which."
class MatchingStrategy(ABC):
    @abstractmethod
    def rank(self, candidates: list[Driver], pickup: Location) -> list[Driver]:
        ...


class NearestDriverStrategy(MatchingStrategy):
    def rank(self, candidates: list[Driver], pickup: Location) -> list[Driver]:
        # WHY: sort by straight-line distance to pickup, closest first.
        return sorted(candidates, key=lambda d: d.location.distance_km(pickup))


# ── GEO INDEX STRATEGY ───────────────────────────────────────────────────────
# 🎙️ "The location index is abstracted so I can start with a simple scan and
#      later drop in a geohash or quadtree with no change to the service."
class DriverLocationIndex(ABC):
    @abstractmethod
    def register(self, driver: Driver) -> None:
        ...

    @abstractmethod
    def nearest_available(self, loc: Location, vtype: VehicleType, k: int) -> list[Driver]:
        ...


class GridLocationIndex(DriverLocationIndex):
    """Holds driver references; filters live status on query.

    n is small per query area, so a scan + sort is fine and obviously correct.
    Production swap: bucket drivers by geohash cell and scan only nearby cells.
    """

    def __init__(self) -> None:
        self._drivers: dict[str, Driver] = {}

    def register(self, driver: Driver) -> None:
        # WHY: store the SAME object reference, so when the driver's status flips
        #      to OFFERED/ON_TRIP the index sees it live — no sync bug.
        self._drivers[driver.id] = driver

    def nearest_available(self, loc: Location, vtype: VehicleType, k: int) -> list[Driver]:
        candidates = [
            d for d in self._drivers.values()
            if d.status == DriverStatus.AVAILABLE and d.vehicle.type == vtype
        ]
        candidates.sort(key=lambda d: d.location.distance_km(loc))
        return candidates[:k]
