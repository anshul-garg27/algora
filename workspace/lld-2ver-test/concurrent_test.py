"""
Multi-threaded test for the thread-safe parking lot.
Demonstrates that concurrent entry/exit gates handle collisions correctly.
"""

import threading
import time
from models import Vehicle, VehicleSize, ParkingSpot, ParkingFloor, NoSpotAvailableError
from parking_lot_threadsafe import ParkingLot, EntryGate, ExitGate


def create_test_lot() -> ParkingLot:
    """Create a lot with limited capacity to force collisions."""
    # Floor 1: 5 compact, 5 normal, 5 large = 15 total
    spots = []
    spot_id = 1
    for _ in range(5):
        spots.append(ParkingSpot(spot_id, VehicleSize.COMPACT, 1))
        spot_id += 1
    for _ in range(5):
        spots.append(ParkingSpot(spot_id, VehicleSize.NORMAL, 1))
        spot_id += 1
    for _ in range(5):
        spots.append(ParkingSpot(spot_id, VehicleSize.LARGE, 1))
        spot_id += 1

    lot = ParkingLot([ParkingFloor(1, spots)], hourly_rate=2.0)
    lot.entry_gate = EntryGate("entry-1", lot)
    lot.exit_gate = ExitGate("exit-1", lot)
    return lot


def test_concurrent_entries_no_double_assignment():
    """
    Test that concurrent entry gates do NOT double-assign the same spot.

    Scenario: 20 vehicles arrive concurrently at 4 entry gates.
    The lot has only 15 spots.
    Expected: 15 vehicles park, 5 are rejected with NoSpotAvailableError.
    Actual occupancy must be exactly 15 (no double-assignment).
    """
    print("\n" + "="*70)
    print("TEST: Concurrent Entry Gates (No Double-Assignment)")
    print("="*70)

    lot = create_test_lot()
    print(f"Initial lot: {lot}")
    print(f"Capacity: 15 spots")

    parked_vehicles = []
    rejected_vehicles = []
    lock = threading.Lock()

    def vehicle_arrival(gate_id: int, vehicle_size: VehicleSize, vehicle_num: int):
        """Simulate a vehicle arriving at a gate."""
        vehicle = Vehicle.create(vehicle_size, f"V-{gate_id}-{vehicle_num}")
        try:
            ticket = lot.entry_gate.process_vehicle(vehicle, timestamp=1000.0)
            with lock:
                parked_vehicles.append((vehicle.id, ticket.spot_id))
            print(f"  Gate {gate_id}: Vehicle {vehicle_num} ({vehicle_size.name:7}) → Spot {ticket.spot_id} ✓")
        except NoSpotAvailableError:
            with lock:
                rejected_vehicles.append(vehicle.id)
            print(f"  Gate {gate_id}: Vehicle {vehicle_num} ({vehicle_size.name:7}) → REJECTED (no spot) ✗")

    # Launch 20 vehicles concurrently from 4 gates
    threads = []
    print(f"\nLaunching 20 vehicles concurrently from 4 gates...")
    for gate_id in range(4):
        for vehicle_num in range(5):
            size = [VehicleSize.COMPACT, VehicleSize.NORMAL, VehicleSize.LARGE][vehicle_num % 3]
            t = threading.Thread(target=vehicle_arrival, args=(gate_id, size, vehicle_num))
            threads.append(t)
            t.start()

    # Wait for all threads to complete
    for t in threads:
        t.join()

    print(f"\nResults:")
    print(f"  Parked: {len(parked_vehicles)} vehicles")
    print(f"  Rejected: {len(rejected_vehicles)} vehicles")
    print(f"  Total attempts: {len(parked_vehicles) + len(rejected_vehicles)}")

    # Verify no double-assignment
    spot_ids = [spot_id for _, spot_id in parked_vehicles]
    unique_spots = set(spot_ids)
    assert len(spot_ids) == len(unique_spots), f"Double-assignment detected! {len(spot_ids)} parked but only {len(unique_spots)} unique spots"
    print(f"  Unique spots used: {len(unique_spots)} ✓ (no double-assignment)")

    # Verify occupancy matches
    occupancy = lot.get_occupancy()
    assert occupancy["occupied"] == len(parked_vehicles), f"Occupancy mismatch: reported {occupancy['occupied']}, actual {len(parked_vehicles)}"
    print(f"  Lot occupancy: {occupancy['occupied']}/{occupancy['total_spots']} ✓")

    assert len(lot.tickets) == len(parked_vehicles), f"Ticket mismatch: {len(lot.tickets)} tickets but {len(parked_vehicles)} vehicles"
    print(f"  Active tickets: {len(lot.tickets)} ✓")

    assert len(parked_vehicles) == 15, f"Expected 15 parked (full), got {len(parked_vehicles)}"
    assert len(rejected_vehicles) == 5, f"Expected 5 rejected, got {len(rejected_vehicles)}"
    print(f"\n✅ TEST PASSED: Concurrent entry is safe; no double-assignment.")


def test_concurrent_exit_doesnt_corrupt_lot():
    """
    Test that concurrent exit gates handle ticket validation correctly.

    Scenario: Park 10 vehicles, then exit 5 concurrently from different gates.
    Expected: 5 exit successfully, 5 remain parked.
    Actual occupancy must be exactly 5 (no corruption).
    """
    print("\n" + "="*70)
    print("TEST: Concurrent Exit Gates (Corruption Resistance)")
    print("="*70)

    lot = create_test_lot()

    # First, park 10 vehicles
    print(f"Parking 10 vehicles...")
    tickets = []
    for i in range(10):
        vehicle = Vehicle.create(VehicleSize.COMPACT, f"PreparePark-{i}")
        ticket = lot.entry_gate.process_vehicle(vehicle, timestamp=1000.0)
        tickets.append(ticket)
        print(f"  Vehicle {i}: → Spot {ticket.spot_id}")

    print(f"Lot occupancy after parking: {lot.get_occupancy()}")

    # Now exit tickets 0-4 concurrently from 2 gates
    exited_tickets = []
    failed_exits = []
    lock = threading.Lock()

    def vehicle_exit(gate_id: int, ticket_idx: int):
        """Simulate a vehicle exiting at a gate."""
        ticket = tickets[ticket_idx]
        try:
            fee = lot.exit_gate.process_vehicle_exit(ticket, timestamp=5000.0)
            with lock:
                exited_tickets.append(ticket.id)
            print(f"  Gate {gate_id}: Ticket {ticket_idx} → Exit fee ${fee:.2f} ✓")
        except Exception as e:
            with lock:
                failed_exits.append(ticket_idx)
            print(f"  Gate {gate_id}: Ticket {ticket_idx} → ERROR: {e} ✗")

    print(f"\nExiting tickets 0-4 concurrently from 2 gates...")
    threads = []
    for gate_id in range(2):
        for ticket_idx in range(5):
            t = threading.Thread(target=vehicle_exit, args=(gate_id, ticket_idx))
            threads.append(t)
            t.start()

    for t in threads:
        t.join()

    print(f"\nResults:")
    print(f"  Exited: {len(exited_tickets)} tickets")
    print(f"  Failed exits: {len(failed_exits)}")

    # Verify final occupancy
    occupancy = lot.get_occupancy()
    expected_occupied = 10 - len(exited_tickets)
    assert occupancy["occupied"] == expected_occupied, f"Occupancy mismatch: expected {expected_occupied}, got {occupancy['occupied']}"
    print(f"  Final occupancy: {occupancy['occupied']}/{occupancy['total_spots']} ✓")

    assert len(lot.tickets) == expected_occupied, f"Ticket mismatch: {len(lot.tickets)} but {expected_occupied} occupied"
    print(f"  Active tickets: {len(lot.tickets)} ✓")

    assert len(exited_tickets) == 5, f"Expected 5 successful exits, got {len(exited_tickets)}"
    print(f"\n✅ TEST PASSED: Concurrent exit is safe; lot integrity preserved.")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("THREAD-SAFE PARKING LOT - CONCURRENCY TEST SUITE")
    print("="*70)

    test_concurrent_entries_no_double_assignment()
    test_concurrent_exit_doesnt_corrupt_lot()

    print("\n" + "="*70)
    print("ALL CONCURRENCY TESTS PASSED ✅")
    print("="*70)
