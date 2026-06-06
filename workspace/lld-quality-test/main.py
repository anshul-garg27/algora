"""
Main driver and test suite for the parking lot system.
"""

from datetime import datetime, timedelta
import time
import threading

from models import Vehicle, VehicleSize, SpotType
from pricing import HourlyPricingStrategy, FlatRatePricingStrategy
from lot import ParkingLot, ParkingFloor


def test_basic_entry_exit():
    """Test a basic park and exit flow."""
    print("\n=== Test: Basic Entry/Exit ===")

    # Create a parking lot with 1 floor, 2 small spots, 2 medium, 2 large, 1 handicap
    floor = ParkingFloor.create(floor_id="F1", small_count=2, medium_count=2, large_count=2, handicap_count=1)
    pricing = HourlyPricingStrategy(hourly_rate=5.0)
    lot = ParkingLot(lot_id="LOT1", floors=[floor], pricing_strategy=pricing)

    # Vehicle 1: Small vehicle enters
    v1 = Vehicle(vehicle_id="V1", license_plate="ABC123", size=VehicleSize.SMALL)
    ticket1 = lot.enter(v1)
    assert ticket1 is not None, "Vehicle 1 should get a ticket"
    assert ticket1.vehicle == v1
    assert ticket1.spot.spot_type == SpotType.SMALL
    print(f"✓ Vehicle 1 (SMALL) parked in spot {ticket1.spot.id}")

    # Check occupancy
    occ = lot.get_occupancy()
    assert occ["occupied"] == 1, f"Should have 1 occupied spot, got {occ['occupied']}"
    print(f"✓ Occupancy: {occ['occupied']} occupied, {occ['available']} available out of {occ['total']} total")

    # Vehicle 2: Medium vehicle enters
    v2 = Vehicle(vehicle_id="V2", license_plate="XYZ789", size=VehicleSize.MEDIUM)
    ticket2 = lot.enter(v2)
    assert ticket2 is not None
    assert ticket2.spot.spot_type == SpotType.MEDIUM
    print(f"✓ Vehicle 2 (MEDIUM) parked in spot {ticket2.spot.id}")

    # Vehicle 1 exits
    fee1 = lot.exit(ticket1)
    assert fee1 == 5.0, f"Fee should be $5.0 for ~1 hour, got ${fee1}"
    print(f"✓ Vehicle 1 exited, fee: ${fee1:.2f}")
    assert ticket1.spot.is_available(), "Spot should be available after exit"
    print(f"✓ Spot {ticket1.spot.id} is now available")

    # Vehicle 2 exits
    fee2 = lot.exit(ticket2)
    assert fee2 == 5.0
    print(f"✓ Vehicle 2 exited, fee: ${fee2:.2f}")

    occ_final = lot.get_occupancy()
    assert occ_final["occupied"] == 0
    print(f"✓ Final occupancy: {occ_final['occupied']} occupied")


def test_no_spot_available():
    """Test rejection when no spot is available."""
    print("\n=== Test: No Spot Available ===")

    # Create a lot with only 1 small spot
    floor = ParkingFloor.create(floor_id="F1", small_count=1, medium_count=0, large_count=0, handicap_count=0)
    pricing = HourlyPricingStrategy(hourly_rate=5.0)
    lot = ParkingLot(lot_id="LOT1", floors=[floor], pricing_strategy=pricing)

    # Vehicle 1 enters
    v1 = Vehicle(vehicle_id="V1", license_plate="ABC123", size=VehicleSize.SMALL)
    ticket1 = lot.enter(v1)
    assert ticket1 is not None
    print(f"✓ Vehicle 1 parked")

    # Vehicle 2 tries to enter (no spot available)
    v2 = Vehicle(vehicle_id="V2", license_plate="XYZ789", size=VehicleSize.SMALL)
    ticket2 = lot.enter(v2)
    assert ticket2 is None, "Vehicle 2 should be rejected (no spot)"
    print(f"✓ Vehicle 2 rejected (no available spot)")


def test_spot_size_matching():
    """Test that vehicles are matched to appropriately sized spots."""
    print("\n=== Test: Spot Size Matching ===")

    floor = ParkingFloor.create(floor_id="F1", small_count=1, medium_count=1, large_count=1, handicap_count=0)
    pricing = HourlyPricingStrategy(hourly_rate=5.0)
    lot = ParkingLot(lot_id="LOT1", floors=[floor], pricing_strategy=pricing)

    # Small vehicle should get a SMALL spot
    v_small = Vehicle(vehicle_id="V_SMALL", license_plate="SM001", size=VehicleSize.SMALL)
    t_small = lot.enter(v_small)
    assert t_small.spot.spot_type == SpotType.SMALL
    print(f"✓ SMALL vehicle got SMALL spot")

    # Medium vehicle should get a MEDIUM spot
    v_medium = Vehicle(vehicle_id="V_MEDIUM", license_plate="MD001", size=VehicleSize.MEDIUM)
    t_medium = lot.enter(v_medium)
    assert t_medium.spot.spot_type == SpotType.MEDIUM
    print(f"✓ MEDIUM vehicle got MEDIUM spot")

    # Large vehicle should get a LARGE spot
    v_large = Vehicle(vehicle_id="V_LARGE", license_plate="LG001", size=VehicleSize.LARGE)
    t_large = lot.enter(v_large)
    assert t_large.spot.spot_type == SpotType.LARGE
    print(f"✓ LARGE vehicle got LARGE spot")

    lot.exit(t_small)
    lot.exit(t_medium)
    lot.exit(t_large)


def test_duplicate_exit():
    """Test that exiting twice with the same ticket fails."""
    print("\n=== Test: Duplicate Exit Prevention ===")

    floor = ParkingFloor.create(floor_id="F1", small_count=1, medium_count=0, large_count=0, handicap_count=0)
    pricing = HourlyPricingStrategy(hourly_rate=5.0)
    lot = ParkingLot(lot_id="LOT1", floors=[floor], pricing_strategy=pricing)

    v = Vehicle(vehicle_id="V1", license_plate="ABC123", size=VehicleSize.SMALL)
    ticket = lot.enter(v)
    assert ticket is not None

    # First exit succeeds
    fee1 = lot.exit(ticket)
    assert fee1 == 5.0
    print(f"✓ First exit succeeded, fee: ${fee1:.2f}")

    # Second exit should fail
    try:
        fee2 = lot.exit(ticket)
        assert False, "Second exit should have raised an error"
    except ValueError as e:
        print(f"✓ Second exit rejected: {e}")


def test_pricing_strategies():
    """Test different pricing strategies."""
    print("\n=== Test: Pricing Strategies ===")

    # Test hourly pricing with longer duration
    floor = ParkingFloor.create(floor_id="F1", small_count=1, medium_count=0, large_count=0, handicap_count=0)
    pricing_hourly = HourlyPricingStrategy(hourly_rate=10.0)
    lot = ParkingLot(lot_id="LOT1", floors=[floor], pricing_strategy=pricing_hourly)

    v = Vehicle(vehicle_id="V1", license_plate="ABC123", size=VehicleSize.SMALL)

    # Manually set entry/exit times to simulate 2.5 hours
    ticket = lot.enter(v)
    ticket.entry_time = datetime.now() - timedelta(hours=2, minutes=30)
    fee = lot.exit(ticket)
    # 2.5 hours rounded up = 3 hours × $10 = $30
    assert fee == 30.0, f"Expected $30.0 for 2.5 hours, got ${fee}"
    print(f"✓ Hourly pricing: 2.5h → ${fee:.2f} (rounded to 3h)")

    # Test flat rate pricing
    floor2 = ParkingFloor.create(floor_id="F1", small_count=1, medium_count=0, large_count=0, handicap_count=0)
    pricing_flat = FlatRatePricingStrategy(flat_rate=15.0)
    lot2 = ParkingLot(lot_id="LOT2", floors=[floor2], pricing_strategy=pricing_flat)

    v2 = Vehicle(vehicle_id="V2", license_plate="XYZ789", size=VehicleSize.SMALL)
    ticket2 = lot2.enter(v2)
    fee2 = lot2.exit(ticket2)
    assert fee2 == 15.0, f"Expected flat rate $15.0, got ${fee2}"
    print(f"✓ Flat rate pricing: any duration → ${fee2:.2f}")


def test_concurrent_entries():
    """Test concurrent entry requests (stress test with threads)."""
    print("\n=== Test: Concurrent Entries ===")

    # Create a lot with limited spots
    floor = ParkingFloor.create(floor_id="F1", small_count=5, medium_count=0, large_count=0, handicap_count=0)
    pricing = HourlyPricingStrategy(hourly_rate=5.0)
    lot = ParkingLot(lot_id="LOT1", floors=[floor], pricing_strategy=pricing)

    tickets = []
    lock = threading.Lock()

    def enter_vehicle(vehicle_id: int):
        """Thread worker: try to park a vehicle."""
        v = Vehicle(
            vehicle_id=f"V{vehicle_id}",
            license_plate=f"VH{vehicle_id:03d}",
            size=VehicleSize.SMALL
        )
        ticket = lot.enter(v)
        if ticket:
            with lock:
                tickets.append(ticket)

    # Try to park 10 vehicles concurrently (only 5 will succeed)
    threads = [threading.Thread(target=enter_vehicle, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Verify exactly 5 succeeded
    assert len(tickets) == 5, f"Expected 5 successful entries, got {len(tickets)}"
    print(f"✓ 10 concurrent attempts → {len(tickets)} successful (5 spots available)")

    occ = lot.get_occupancy()
    assert occ["occupied"] == 5
    print(f"✓ Occupancy verified: {occ['occupied']}/5 spots occupied")


def test_invalid_inputs():
    """Test that invalid inputs are rejected."""
    print("\n=== Test: Invalid Inputs ===")

    floor = ParkingFloor.create(floor_id="F1", small_count=1, medium_count=0, large_count=0, handicap_count=0)
    pricing = HourlyPricingStrategy(hourly_rate=5.0)
    lot = ParkingLot(lot_id="LOT1", floors=[floor], pricing_strategy=pricing)

    # None vehicle should raise
    try:
        lot.enter(None)
        assert False, "Should reject None vehicle"
    except (ValueError, TypeError) as e:
        print(f"✓ None vehicle rejected: {type(e).__name__}")

    # Invalid ticket should raise
    try:
        from models import ParkingTicket
        bad_ticket = ParkingTicket(
            ticket_id="FAKE",
            vehicle=Vehicle("V_FAKE", "FAKE", VehicleSize.SMALL),
            spot=None,
            entry_time=datetime.now()
        )
        lot.exit(bad_ticket)
        assert False, "Should reject unknown ticket"
    except ValueError as e:
        print(f"✓ Unknown ticket rejected: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("PARKING LOT SYSTEM - TEST SUITE")
    print("=" * 60)

    test_basic_entry_exit()
    test_no_spot_available()
    test_spot_size_matching()
    test_duplicate_exit()
    test_pricing_strategies()
    test_concurrent_entries()
    test_invalid_inputs()

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED ✓")
    print("=" * 60)
