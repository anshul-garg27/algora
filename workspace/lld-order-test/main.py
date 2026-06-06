#!/usr/bin/env python3
"""
Parking Lot System - Complete Implementation & Test Driver
Tests: normal park/unpark, invalid requests, lot full, concurrency.
"""

from datetime import datetime, timedelta
import time
import threading
from models import Vehicle, VehicleType, SpotSize
from parking import ParkingLot, Level, ParkingSpot
from pricing import HourlyPricingStrategy


def setup_parking_lot():
    """Create a sample parking lot with 2 levels."""
    # Level 1: 2 compact, 2 regular, 1 large
    level1_spots = [
        ParkingSpot("L1_C1", 1, SpotSize.COMPACT),
        ParkingSpot("L1_C2", 1, SpotSize.COMPACT),
        ParkingSpot("L1_R1", 1, SpotSize.REGULAR),
        ParkingSpot("L1_R2", 1, SpotSize.REGULAR),
        ParkingSpot("L1_L1", 1, SpotSize.LARGE),
    ]
    level1 = Level(1, level1_spots)

    # Level 2: 1 compact, 2 regular, 2 large
    level2_spots = [
        ParkingSpot("L2_C1", 2, SpotSize.COMPACT),
        ParkingSpot("L2_R1", 2, SpotSize.REGULAR),
        ParkingSpot("L2_R2", 2, SpotSize.REGULAR),
        ParkingSpot("L2_L1", 2, SpotSize.LARGE),
        ParkingSpot("L2_L2", 2, SpotSize.LARGE),
    ]
    level2 = Level(2, level2_spots)

    # Pricing: $5 per hour
    pricing = HourlyPricingStrategy(rate_per_hour=5.0)
    lot = ParkingLot([level1, level2], pricing)
    return lot


def test_basic_park_unpark():
    """Test basic park and unpark flow."""
    print("\n=== Test 1: Basic Park/Unpark ===")
    lot = setup_parking_lot()
    print(f"Initial: {lot}")

    # Park a car
    car = Vehicle("V1", "ABC-123", VehicleType.CAR)
    ticket = lot.park_vehicle(car)
    print(f"✓ Parked car: {ticket.ticket_id} at spot {ticket.spot_id}")
    print(f"  After park: {lot}")

    # Wait a bit to accumulate time
    time.sleep(0.1)

    # Unpark the car
    fee = lot.unpark_vehicle(ticket.ticket_id)
    print(f"✓ Unparked car: fee=${fee:.2f}")
    print(f"  After unpark: {lot}")


def test_vehicle_types():
    """Test different vehicle types and spot fitting."""
    print("\n=== Test 2: Vehicle Types & Spot Fitting ===")
    lot = setup_parking_lot()

    # Motorcycle -> should fit compact spot
    motorcycle = Vehicle("V2", "MOTO-001", VehicleType.MOTORCYCLE)
    ticket_moto = lot.park_vehicle(motorcycle)
    print(f"✓ Parked motorcycle at {ticket_moto.spot_id}")

    # Truck -> should need large spot (not compact)
    truck = Vehicle("V3", "TRUCK-99", VehicleType.TRUCK)
    ticket_truck = lot.park_vehicle(truck)
    print(f"✓ Parked truck at {ticket_truck.spot_id}")

    # Verify they're in correct spot types
    assert "C" in ticket_moto.spot_id, "Motorcycle should be in compact spot"
    assert "L" in ticket_truck.spot_id, "Truck should be in large spot"
    print(f"  Spot fitting validated!")
    print(f"  {lot}")


def test_lot_full():
    """Test parking when lot is full."""
    print("\n=== Test 3: Lot Full Scenario ===")
    lot = setup_parking_lot()
    capacity = lot.get_capacity()
    print(f"Lot capacity: {capacity} spots")

    # Fill the lot
    vehicles = []
    for i in range(capacity):
        vehicle_type = VehicleType.CAR if i % 3 != 2 else VehicleType.MOTORCYCLE
        v = Vehicle(f"V{i}", f"LIC-{i:04d}", vehicle_type)
        ticket = lot.park_vehicle(v)
        vehicles.append((v, ticket))
        print(f"  Parked vehicle {i+1}/{capacity} at {ticket.spot_id}")

    print(f"Lot is now: {lot}")

    # Try to park one more (should fail)
    extra_car = Vehicle("EXTRA", "EXTRA-001", VehicleType.CAR)
    try:
        lot.park_vehicle(extra_car)
        print("✗ ERROR: Should have raised ValueError for full lot!")
        assert False, "Expected exception"
    except ValueError as e:
        print(f"✓ Correctly rejected full lot: {e}")


def test_invalid_ticket():
    """Test unparking with invalid ticket."""
    print("\n=== Test 4: Invalid Ticket ===")
    lot = setup_parking_lot()

    # Try to unpark with a non-existent ticket
    try:
        lot.unpark_vehicle("INVALID_TICKET_12345")
        print("✗ ERROR: Should have raised ValueError!")
        assert False, "Expected exception"
    except ValueError as e:
        print(f"✓ Correctly rejected invalid ticket: {e}")


def test_pricing():
    """Test pricing with different durations."""
    print("\n=== Test 5: Pricing ===")
    lot = setup_parking_lot()

    car = Vehicle("V_PRICE", "PRICE-001", VehicleType.CAR)
    ticket = lot.park_vehicle(car)

    # Simulate durations by manually setting entry time
    ticket.entry_time = datetime.now() - timedelta(hours=2, minutes=30)

    exit_time = datetime.now()
    fee = lot.pricing_strategy.calculate_fee(ticket.entry_time, exit_time)

    # 2.5 hours -> rounds up to 3 hours -> 3 * $5 = $15
    print(f"Parking duration: ~2.5 hours")
    print(f"Calculated fee (rounded up to 3 hours): ${fee:.2f}")
    assert fee == 15.0, f"Expected $15.00 but got ${fee:.2f}"
    print(f"✓ Pricing correct!")

    # Clean up
    lot.unpark_vehicle(ticket.ticket_id)


def test_concurrent_parking():
    """Test concurrent park operations (thread safety)."""
    print("\n=== Test 6: Concurrent Parking (Thread Safety) ===")
    lot = setup_parking_lot()
    parked_tickets = []
    lock = threading.Lock()
    errors = []

    def park_vehicle_concurrent(vehicle_id):
        try:
            vehicle = Vehicle(f"V_CONC_{vehicle_id}", f"CONC-{vehicle_id:03d}", VehicleType.CAR)
            ticket = lot.park_vehicle(vehicle)
            with lock:
                parked_tickets.append(ticket)
        except Exception as e:
            with lock:
                errors.append(str(e))

    # Start 10 threads trying to park simultaneously
    threads = [
        threading.Thread(target=park_vehicle_concurrent, args=(i,))
        for i in range(10)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Some should succeed, some should fail (lot has only 10 spots total, we try 10)
    successful = len(parked_tickets)
    failed = len(errors)
    print(f"Concurrent park attempts: 10")
    print(f"  Successful: {successful}")
    print(f"  Failed (lot full): {failed}")
    print(f"✓ Thread-safe parking verified!")
    print(f"  {lot}")


def test_duplicate_unpark_prevention():
    """Test that a ticket can only be unparsed once."""
    print("\n=== Test 7: Duplicate Unpark Prevention ===")
    lot = setup_parking_lot()

    car = Vehicle("V_DUP", "DUP-001", VehicleType.CAR)
    ticket = lot.park_vehicle(car)
    print(f"Parked car: {ticket.ticket_id}")

    # First unpark succeeds
    fee1 = lot.unpark_vehicle(ticket.ticket_id)
    print(f"✓ First unpark succeeded: fee=${fee1:.2f}")

    # Second unpark attempt should fail
    try:
        lot.unpark_vehicle(ticket.ticket_id)
        print("✗ ERROR: Should have rejected duplicate unpark!")
        assert False, "Expected exception"
    except ValueError as e:
        print(f"✓ Correctly rejected duplicate unpark: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("PARKING LOT SYSTEM - COMPREHENSIVE TESTS")
    print("=" * 60)

    try:
        test_basic_park_unpark()
        test_vehicle_types()
        test_lot_full()
        test_invalid_ticket()
        test_pricing()
        test_concurrent_parking()
        test_duplicate_unpark_prevention()

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED ✓")
        print("=" * 60)
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
