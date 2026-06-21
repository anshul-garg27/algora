"""Driver + assertions. Exercises happy path, no-drivers, invalid inputs,
duplicates, state-machine guards, payment retry + permanent failure, cancel,
and a 50-thread concurrency race for a single driver.
"""
from __future__ import annotations

import threading

from models import (
    Driver, InvalidTripState, Location, PaymentFailed, Rider, RiderOnActiveTrip,
    TripStatus, UnknownEntity, Vehicle, VehicleType,
)
from payments import AlwaysSuccessGateway, PaymentService, ScriptedGateway
from ride_service import RideService, ThreadSafeRideService, TripObserver
from strategies import GridLocationIndex, NearestDriverStrategy, SurgePricingStrategy


class PrintObserver(TripObserver):
    def __init__(self) -> None:
        self.events: list[str] = []

    def on_event(self, trip, event) -> None:
        self.events.append(event)


def make_service(gateway=None, surge=1.0):
    gateway = gateway or AlwaysSuccessGateway()
    svc = RideService(
        matching=NearestDriverStrategy(),
        pricing=SurgePricingStrategy(surge_fn=lambda loc: surge),
        index=GridLocationIndex(),
        payments=PaymentService(gateway),
    )
    return svc


DT = Location(37.7749, -122.4194)        # SF downtown
NEAR = Location(37.7750, -122.4180)      # ~150 m away
FAR = Location(37.8044, -122.2712)       # Oakland
DROP = Location(37.7849, -122.4094)


def case_happy_path():
    svc = make_service()
    svc.register_rider(Rider("r1", "Alice"))
    near = Driver("d1", "Bob", Vehicle("v1", VehicleType.UBERX, "ABC"), NEAR)
    far = Driver("d2", "Carl", Vehicle("v2", VehicleType.UBERX, "XYZ"), FAR)
    svc.register_driver(far)
    svc.register_driver(near)
    obs = PrintObserver()
    svc.add_observer(obs)

    trip = svc.request_ride("r1", DT, DROP, VehicleType.UBERX)
    assert trip.status == TripStatus.DRIVER_ASSIGNED
    assert trip.driver_id == "d1", "nearest driver must be chosen"   # matching works
    assert near.status.name == "OFFERED"

    svc.accept_ride(trip.id, "d1")
    assert trip.status == TripStatus.EN_ROUTE and near.status.name == "ON_TRIP"
    svc.start_trip(trip.id)
    assert trip.status == TripStatus.IN_PROGRESS
    svc.complete_trip(trip.id)
    assert trip.status == TripStatus.COMPLETED
    assert trip.payment_id is not None
    assert near.status.name == "AVAILABLE", "driver freed after completion"
    assert obs.events == ["DRIVER_ASSIGNED", "EN_ROUTE", "IN_PROGRESS", "COMPLETED"]
    print(f"  happy path OK  fare=${trip.fare.total}  events={obs.events}")


def case_no_drivers():
    svc = make_service()
    svc.register_rider(Rider("r1", "Alice"))
    trip = svc.request_ride("r1", DT, DROP, VehicleType.UBERX)
    assert trip.status == TripStatus.NO_DRIVERS, "must end with defined NO_DRIVERS outcome"
    # rider was freed, so they can request again
    trip2 = svc.request_ride("r1", DT, DROP, VehicleType.UBERX)
    assert trip2.status == TripStatus.NO_DRIVERS
    print("  no-drivers OK  (rider freed, request never silently dropped)")


def case_vehicle_type_filter():
    svc = make_service()
    svc.register_rider(Rider("r1", "Alice"))
    svc.register_driver(Driver("d1", "Bob", Vehicle("v1", VehicleType.UBERBLACK, "B"), NEAR))
    trip = svc.request_ride("r1", DT, DROP, VehicleType.UBERX)  # no UberX online
    assert trip.status == TripStatus.NO_DRIVERS
    print("  vehicle-type filter OK  (Black driver not matched to UberX request)")


def case_invalid_inputs():
    svc = make_service()
    svc.register_rider(Rider("r1", "Alice"))
    svc.register_driver(Driver("d1", "Bob", Vehicle("v1", VehicleType.UBERX, "B"), NEAR))

    try:
        svc.request_ride("ghost", DT, DROP, VehicleType.UBERX)
        assert False
    except UnknownEntity:
        pass

    t = svc.request_ride("r1", DT, DROP, VehicleType.UBERX)  # rider now active
    try:
        svc.request_ride("r1", DT, DROP, VehicleType.UBERX)
        assert False
    except RiderOnActiveTrip:
        pass

    # invalid transition: start before accept
    try:
        svc.start_trip(t.id)
        assert False
    except InvalidTripState:
        pass

    try:
        svc.get_trip("trip-999")
        assert False
    except UnknownEntity:
        pass
    print("  invalid-input guards OK  (unknown rider, double request, bad transition, unknown trip)")


def case_payment_retry():
    # fail once, then succeed -> PaymentService retries internally
    svc = make_service(gateway=ScriptedGateway([False, True]))
    svc.register_rider(Rider("r1", "Alice"))
    d = Driver("d1", "Bob", Vehicle("v1", VehicleType.UBERX, "B"), NEAR)
    svc.register_driver(d)
    t = svc.request_ride("r1", DT, DROP, VehicleType.UBERX)
    svc.accept_ride(t.id, "d1")
    svc.start_trip(t.id)
    svc.complete_trip(t.id)
    assert t.status == TripStatus.COMPLETED, "retry should make completion succeed"

    # idempotency: charging same trip again returns same payment, no double charge
    p_again = svc._payments.charge_for_trip(t.id, t.fare.total)
    assert p_again.id == t.payment_id
    print("  payment retry + idempotency OK")


def case_payment_permanent_failure():
    svc = make_service(gateway=ScriptedGateway([False]))  # always fails
    svc.register_rider(Rider("r1", "Alice"))
    svc.register_driver(Driver("d1", "Bob", Vehicle("v1", VehicleType.UBERX, "B"), NEAR))
    t = svc.request_ride("r1", DT, DROP, VehicleType.UBERX)
    svc.accept_ride(t.id, "d1")
    svc.start_trip(t.id)
    try:
        svc.complete_trip(t.id)
        assert False
    except PaymentFailed:
        pass
    assert t.status == TripStatus.IN_PROGRESS, "trip stays IN_PROGRESS so it can retry"
    print("  payment permanent-failure OK  (trip not lost, stays IN_PROGRESS)")


def case_cancel():
    svc = make_service()
    svc.register_rider(Rider("r1", "Alice"))
    d = Driver("d1", "Bob", Vehicle("v1", VehicleType.UBERX, "B"), NEAR)
    svc.register_driver(d)
    t = svc.request_ride("r1", DT, DROP, VehicleType.UBERX)
    svc.cancel_trip(t.id)
    assert t.status == TripStatus.CANCELLED
    assert d.status.name == "AVAILABLE", "cancelled trip frees the driver"
    # rider freed -> can request again and get the same driver back
    t2 = svc.request_ride("r1", DT, DROP, VehicleType.UBERX)
    assert t2.status == TripStatus.DRIVER_ASSIGNED and t2.driver_id == "d1"
    print("  cancel OK  (driver released, rider freed)")


def case_concurrency_one_driver():
    # 50 riders, 1 available driver -> exactly 1 DRIVER_ASSIGNED, 49 NO_DRIVERS
    svc = ThreadSafeRideService(
        matching=NearestDriverStrategy(),
        pricing=SurgePricingStrategy(),
        index=GridLocationIndex(),
        payments=PaymentService(AlwaysSuccessGateway()),
    )
    N = 50
    for i in range(N):
        svc.register_rider(Rider(f"r{i}", f"rider{i}"))
    svc.register_driver(Driver("d1", "Bob", Vehicle("v1", VehicleType.UBERX, "B"), NEAR))

    assigned: list[str] = []
    no_drivers: list[str] = []
    lock = threading.Lock()
    barrier = threading.Barrier(N)

    def attempt(rid: str):
        barrier.wait()  # all 50 hit request_ride at the same instant
        trip = svc.request_ride(rid, DT, DROP, VehicleType.UBERX)
        with lock:
            (assigned if trip.status == TripStatus.DRIVER_ASSIGNED else no_drivers).append(rid)

    threads = [threading.Thread(target=attempt, args=(f"r{i}",)) for i in range(N)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(assigned) == 1, f"exactly one rider should win, got {len(assigned)}"
    assert len(no_drivers) == N - 1
    print(f"  concurrency OK  {len(assigned)} assigned, {len(no_drivers)} got NO_DRIVERS (no double-booking)")


if __name__ == "__main__":
    print("Running ride-hailing LLD demo:")
    case_happy_path()
    case_no_drivers()
    case_vehicle_type_filter()
    case_invalid_inputs()
    case_payment_retry()
    case_payment_permanent_failure()
    case_cancel()
    case_concurrency_one_driver()
    print("ALL ASSERTIONS PASSED")
