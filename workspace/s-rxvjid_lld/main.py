"""Driver + assertions exercising tricky cases."""
from concurrent.futures import ThreadPoolExecutor
from models import (VehicleType, SpotType, ParkingSpot, ParkingFloor, VehicleFactory)
from strategies import HourlyPricing, CashPayment, CardPayment
from parking_lot import ParkingLot, LotFullError


def build_lot():
    f0 = ParkingFloor(0)
    f1 = ParkingFloor(1)
    # Floor 0: 1 small, 1 medium, 1 large.  Floor 1: 2 medium.
    f0.add_spot(ParkingSpot("0-S1", SpotType.SMALL))
    f0.add_spot(ParkingSpot("0-M1", SpotType.MEDIUM))
    f0.add_spot(ParkingSpot("0-L1", SpotType.LARGE))
    f1.add_spot(ParkingSpot("1-M1", SpotType.MEDIUM))
    f1.add_spot(ParkingSpot("1-M2", SpotType.MEDIUM))
    return ParkingLot([f0, f1])


def main():
    lot = build_lot()
    car = VehicleFactory.create

    # 1) Validation: bad input rejected before mutating state.
    try:
        lot.enter(None, now=0); assert False
    except ValueError:
        print("OK  null vehicle rejected")

    # 2) Happy path: car gets nearest smallest-fitting spot (MEDIUM on floor 0).
    t = lot.enter(car(VehicleType.CAR, "KA01"), now=0)
    assert t.spot.id == "0-M1", t.spot.id
    print("OK  car parked at", t.spot.id)

    # 3) Fit-up: motorcycle takes the SMALL before climbing sizes.
    tm = lot.enter(car(VehicleType.MOTORCYCLE, "KA02"), now=0)
    assert tm.spot.id == "0-S1", tm.spot.id
    print("OK  bike parked at", tm.spot.id)

    # 4) Truck needs LARGE -> only 0-L1.
    tt = lot.enter(car(VehicleType.TRUCK, "KA03"), now=0)
    assert tt.spot.id == "0-L1"
    # Next truck: no LARGE left -> explicit rejection, not silent drop.
    try:
        lot.enter(car(VehicleType.TRUCK, "KA04"), now=0); assert False
    except LotFullError:
        print("OK  second truck rejected (no large spot)")

    # 5) Exit & pricing: car parked 2.5h -> ceil = 3h x 20 = 60.
    pay = lot.exit(t.id, CardPayment(), now=2.5 * 3600)
    assert pay.amount == 60.0 and pay.paid, pay.amount
    print("OK  car billed", pay.amount)

    # 6) Double-exit / unknown ticket rejected.
    try:
        lot.exit(t.id, CashPayment(), now=0); assert False
    except KeyError:
        print("OK  reused ticket rejected")

    # 7) Concurrency: 20 cars race for limited MEDIUM spots; no double-allocation.
    lot2 = build_lot()  # cars fit MEDIUM/LARGE -> capacity = 1 med(f0)+1 large(f0)+2 med(f1)=4
    issued, full = [], 0
    def worker(i):
        nonlocal full
        try:
            issued.append(lot2.enter(car(VehicleType.CAR, f"C{i}"), now=0))
        except LotFullError:
            full += 1
    with ThreadPoolExecutor(max_workers=20) as ex:
        list(ex.map(worker, range(20)))
    spots = [tk.spot.id for tk in issued]
    assert len(spots) == len(set(spots)), "double allocation!"
    assert len(issued) == 4 and full == 16, (len(issued), full)
    print(f"OK  concurrent: {len(issued)} parked uniquely, {full} rejected")

    print("\nAvailability:", lot.availability())
    print("Active tickets:", lot.active_count())
    print("\nALL ASSERTIONS PASSED")


if __name__ == "__main__":
    main()
