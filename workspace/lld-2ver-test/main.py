"""
Main driver and test suite for the parking lot design.
Demonstrates entry, exit, occupancy tracking, and error handling.
"""

from models import (
    Vehicle, VehicleSize, ParkingSpot, ParkingFloor, Ticket,
    NoSpotAvailableError, InvalidTicketError
)
from parking_lot import ParkingLot, EntryGate, ExitGate


def create_sample_lot() -> ParkingLot:
    """Create a sample lot with 2 floors, varied spot sizes."""
    # Floor 1: 2 compact, 2 normal, 1 large
    floor1_spots = [
        ParkingSpot(1, VehicleSize.COMPACT, 1),
        ParkingSpot(2, VehicleSize.COMPACT, 1),
        ParkingSpot(3, VehicleSize.NORMAL, 1),
        ParkingSpot(4, VehicleSize.NORMAL, 1),
        ParkingSpot(5, VehicleSize.LARGE, 1),
    ]
    floor1 = ParkingFloor(1, floor1_spots)

    # Floor 2: 1 compact, 3 normal, 2 large
    floor2_spots = [
        ParkingSpot(6, VehicleSize.COMPACT, 2),
        ParkingSpot(7, VehicleSize.NORMAL, 2),
        ParkingSpot(8, VehicleSize.NORMAL, 2),
        ParkingSpot(9, VehicleSize.NORMAL, 2),
        ParkingSpot(10, VehicleSize.LARGE, 2),
        ParkingSpot(11, VehicleSize.LARGE, 2),
    ]
    floor2 = ParkingFloor(2, floor2_spots)

    lot = ParkingLot([floor1, floor2], hourly_rate=2.0)
    lot.entry_gate = EntryGate("entry-1", lot)
    lot.exit_gate = ExitGate("exit-1", lot)
    return lot


def test_basic_entry_exit():
    """Test basic entry and exit flow."""
    print("\n" + "="*70)
    print("TEST 1: Basic Entry & Exit")
    print("="*70)

    lot = create_sample_lot()
    print(f"Initial lot: {lot}")
    print(f"Occupancy: {lot.get_occupancy()}")

    # Vehicle 1: Compact car arrives
    vehicle1 = Vehicle.create(VehicleSize.COMPACT, "ABC123")
    print(f"\n→ Vehicle 1 (compact, {vehicle1.id[:8]}...) arrives at entry gate")
    ticket1 = lot.entry_gate.process_vehicle(vehicle1, timestamp=1000.0)
    print(f"✓ Ticket issued: {ticket1.id[:8]}... for spot {ticket1.spot_id}")
    print(f"  Lot now: {lot}")
    print(f"  Occupancy: {lot.get_occupancy()}")

    # Vehicle 2: Normal car arrives
    vehicle2 = Vehicle.create(VehicleSize.NORMAL, "XYZ789")
    print(f"\n→ Vehicle 2 (normal, {vehicle2.id[:8]}...) arrives at entry gate")
    ticket2 = lot.entry_gate.process_vehicle(vehicle2, timestamp=1100.0)
    print(f"✓ Ticket issued: {ticket2.id[:8]}... for spot {ticket2.spot_id}")
    print(f"  Lot now: {lot}")
    print(f"  Occupancy: {lot.get_occupancy()}")

    # Vehicle 1 exits after 1 hour (1000 + 3600 = 4600)
    print(f"\n→ Vehicle 1 exits at timestamp 4600.0 (1 hour later)")
    fee1 = lot.exit_gate.process_vehicle_exit(ticket1, timestamp=4600.0)
    print(f"✓ Fee: ${fee1:.2f}")
    print(f"  Lot now: {lot}")
    print(f"  Occupancy: {lot.get_occupancy()}")

    # Vehicle 2 exits after 2.5 hours (1100 + 9000 = 10100)
    print(f"\n→ Vehicle 2 exits at timestamp 10100.0 (2.5 hours later)")
    fee2 = lot.exit_gate.process_vehicle_exit(ticket2, timestamp=10100.0)
    print(f"✓ Fee: ${fee2:.2f} (2.5 hours → 3 hours billed)")
    print(f"  Lot now: {lot}")
    print(f"  Occupancy: {lot.get_occupancy()}")

    assert lot.get_occupancy()["occupied"] == 0, "Lot should be empty"
    assert len(lot.tickets) == 0, "No active tickets"
    print("\n✅ TEST 1 PASSED")


def test_no_spot_available():
    """Test error handling when no spot is available."""
    print("\n" + "="*70)
    print("TEST 2: No Spot Available (Capacity Full)")
    print("="*70)

    lot = create_sample_lot()
    print(f"Initial lot: {lot}")
    print(f"Occupancy: {lot.get_occupancy()}")
    total_spots = lot.get_occupancy()["total_spots"]

    # Fill all available spots (11 total)
    print(f"\n→ Parking {total_spots} vehicles to fill entire lot")
    tickets = []
    size_cycle = [VehicleSize.COMPACT, VehicleSize.NORMAL, VehicleSize.LARGE]
    for i in range(total_spots):
        vehicle = Vehicle.create(size_cycle[i % 3], f"V{i+1}")
        ticket = lot.entry_gate.process_vehicle(vehicle, timestamp=1000.0 + i * 100)
        tickets.append((vehicle, ticket))
        print(f"  Vehicle {i+1:2d}: {vehicle.id[:8]}... ({vehicle.size.name:7}) → Spot {ticket.spot_id}")

    print(f"  Lot now: {lot}")
    print(f"  Occupancy: {lot.get_occupancy()}")

    # Try to park one more vehicle → should fail (lot is full)
    print(f"\n→ Attempting to park one more vehicle when lot is FULL (should fail)")
    vehicle_fail = Vehicle.create(VehicleSize.COMPACT, "OVERFLOW")
    try:
        lot.entry_gate.process_vehicle(vehicle_fail, timestamp=2200.0)
        assert False, "Should have raised NoSpotAvailableError"
    except NoSpotAvailableError as e:
        print(f"✓ Expected error: {e}")

    print(f"  Lot still: {lot}")
    print(f"  Occupancy: {lot.get_occupancy()}")
    print("\n✅ TEST 2 PASSED")


def test_invalid_ticket():
    """Test error handling for invalid tickets on exit."""
    print("\n" + "="*70)
    print("TEST 3: Invalid Ticket (Not Found / Already Exited)")
    print("="*70)

    lot = create_sample_lot()
    vehicle = Vehicle.create(VehicleSize.NORMAL, "NORMAL1")
    ticket = lot.entry_gate.process_vehicle(vehicle, timestamp=1000.0)
    print(f"Vehicle parked: {vehicle.id[:8]}... with ticket {ticket.id[:8]}...")

    # Exit normally
    print(f"\n→ Vehicle exits normally at timestamp 5000.0")
    fee = lot.exit_gate.process_vehicle_exit(ticket, timestamp=5000.0)
    print(f"✓ Fee: ${fee:.2f}")
    print(f"  Occupancy: {lot.get_occupancy()}")

    # Try to exit with the same ticket again → should fail
    print(f"\n→ Attempting to exit with the same ticket again (should fail)")
    try:
        lot.exit_gate.process_vehicle_exit(ticket, timestamp=6000.0)
        assert False, "Should have raised InvalidTicketError"
    except InvalidTicketError as e:
        print(f"✓ Expected error: {e}")

    # Try to exit with a nonexistent ticket
    print(f"\n→ Attempting to exit with a fake ticket (should fail)")
    fake_ticket = Ticket.create("fake-vehicle", 999, 1000.0)
    try:
        lot.exit_gate.process_vehicle_exit(fake_ticket, timestamp=6000.0)
        assert False, "Should have raised InvalidTicketError"
    except InvalidTicketError as e:
        print(f"✓ Expected error: {e}")

    print("\n✅ TEST 3 PASSED")


def test_spot_size_matching():
    """Test that vehicles are matched to appropriately-sized spots."""
    print("\n" + "="*70)
    print("TEST 4: Spot Size Matching (Smallest-First Strategy)")
    print("="*70)

    lot = create_sample_lot()
    print(f"Initial lot: {lot}")

    # Park a compact vehicle → should get the first available compact spot (spot 1)
    print(f"\n→ Compact vehicle arrives")
    compact = Vehicle.create(VehicleSize.COMPACT, "COMPACT1")
    t1 = lot.entry_gate.process_vehicle(compact, timestamp=1000.0)
    print(f"  → Assigned to spot {t1.spot_id} (should be 1 or 2, a compact spot)")
    assert t1.spot_id in [1, 2], "Should be assigned to a compact spot"

    # Park a normal vehicle → should get a normal spot, not waste a large spot
    print(f"\n→ Normal vehicle arrives")
    normal = Vehicle.create(VehicleSize.NORMAL, "NORMAL1")
    t2 = lot.entry_gate.process_vehicle(normal, timestamp=1100.0)
    print(f"  → Assigned to spot {t2.spot_id} (should be 3 or 4, a normal spot)")
    assert t2.spot_id in [3, 4, 7, 8, 9], "Should be assigned to a normal spot, not large"

    # Park a large vehicle → should only get a large spot
    print(f"\n→ Large vehicle arrives")
    large = Vehicle.create(VehicleSize.LARGE, "LARGE1")
    t3 = lot.entry_gate.process_vehicle(large, timestamp=1200.0)
    print(f"  → Assigned to spot {t3.spot_id} (should be 5, 10, or 11, a large spot)")
    assert t3.spot_id in [5, 10, 11], "Should be assigned to a large spot"

    print(f"\nFinal lot: {lot}")
    print("\n✅ TEST 4 PASSED")


def test_concurrent_entries():
    """Simulate concurrent vehicle arrivals (demonstrates the check-then-act critical section)."""
    print("\n" + "="*70)
    print("TEST 5: Concurrent Entry Simulation (Single-Threaded Trace)")
    print("="*70)

    lot = create_sample_lot()
    print(f"Initial lot: {lot}")
    print(f"Available compact spots: {lot.get_available_spot_count(VehicleSize.COMPACT)}")

    # Simulate multiple vehicles arriving "simultaneously"
    # In a real concurrent system, find_and_assign_spot() would be protected by a lock
    print(f"\n→ Simulating 5 vehicles arriving in rapid succession")
    vehicles = []
    tickets = []
    for i in range(5):
        v = Vehicle.create([VehicleSize.COMPACT, VehicleSize.NORMAL, VehicleSize.LARGE][i % 3], f"V{i+1}")
        try:
            t = lot.entry_gate.process_vehicle(v, timestamp=1000.0 + i)
            vehicles.append(v)
            tickets.append(t)
            print(f"  {i+1}. Vehicle {v.id[:8]}... ({v.size.name:7}) → Spot {t.spot_id}")
        except NoSpotAvailableError:
            print(f"  {i+1}. Vehicle {v.id[:8]}... ({v.size.name:7}) → NO SPOT AVAILABLE")

    print(f"\nFinal lot: {lot}")
    print(f"Occupancy: {lot.get_occupancy()}")
    assert len(lot.tickets) == len(tickets), "Tickets should match parked vehicles"
    print("\n✅ TEST 5 PASSED")


def test_fee_calculation():
    """Test parking fee calculation with various durations."""
    print("\n" + "="*70)
    print("TEST 6: Fee Calculation (Rounding Up to Nearest Hour)")
    print("="*70)

    lot = create_sample_lot()

    test_cases = [
        (1000.0, 1000.0, 0.0, "< 1 minute"),  # 0 hours → 1 hour billed
        (1000.0, 4600.0, 1.0, "1 hour"),      # 3600 sec = 1 hour → 1 hour billed
        (1000.0, 5400.0, 1.0, "1.5 hours"),   # 4400 sec = 1.22 hours → 2 hours billed
        (1000.0, 9000.0, 2.22, "2.22 hours"), # 8000 sec = 2.22 hours → 3 hours billed
    ]

    for entry_time, exit_time, duration_label, description in test_cases:
        vehicle = Vehicle.create(VehicleSize.COMPACT, f"TEST-{description.replace(' ', '_')}")
        ticket = lot.entry_gate.process_vehicle(vehicle, timestamp=entry_time)
        fee = lot.exit_gate.process_vehicle_exit(ticket, timestamp=exit_time)
        duration_hours = (exit_time - entry_time) / 3600.0
        billable = max(1, int(duration_hours) + (1 if duration_hours % 1 > 0 else 0))
        expected_fee = billable * 2.0  # $2/hour

        print(f"  Duration: {description:12} ({duration_hours:.2f}h) → Billed: {billable}h → Fee: ${fee:.2f} (expected: ${expected_fee:.2f})")
        assert fee == expected_fee, f"Fee mismatch for {description}"

    print("\n✅ TEST 6 PASSED")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("PARKING LOT DESIGN - COMPREHENSIVE TEST SUITE")
    print("="*70)

    test_basic_entry_exit()
    test_no_spot_available()
    test_invalid_ticket()
    test_spot_size_matching()
    test_concurrent_entries()
    test_fee_calculation()

    print("\n" + "="*70)
    print("ALL TESTS PASSED ✅")
    print("="*70)
