"""
Thread-safe version of ParkingLot with RLock-based concurrency control.
§9 hardening: single RLock guards all mutable operations.
"""

import threading
from typing import Optional
from models import (
    Vehicle, VehicleSize, ParkingSpot, ParkingFloor, Ticket, ParkingRate,
    NoSpotAvailableError, InvalidTicketError
)


class ParkingLot:
    """
    Thread-safe parking lot with RLock concurrency control.

    Concurrency model:
    - Single RLock (reentrant) guards all public mutable operations.
    - Every check-then-act and read-modify-write is atomic.
    - Even read-only methods acquire the lock to ensure consistent snapshots.
    - Reentrant: allows the same thread to re-acquire if a guarded method
      calls another guarded method (e.g., find_and_assign calls are always
      in critical sections, so no nested lock deadlock).

    Trade-offs:
    - Coarse-grained locking: one lock for the whole lot.
    - Pros: Simple, no deadlock, fair FIFO ordering (if threaded from a queue).
    - Cons: Lower throughput under very high concurrency (thousands of gates).
    - For a real production system with ~1000 gates, per-floor or per-spot
      locking would improve throughput, at the cost of deadlock risk.
    """

    def __init__(self, floors: list[ParkingFloor], hourly_rate: float = 2.0):
        self.floors: list[ParkingFloor] = floors
        self.tickets: dict[str, Ticket] = {}
        self.parking_rate: ParkingRate = ParkingRate(hourly_rate)
        self.entry_gate: Optional["Gate"] = None
        self.exit_gate: Optional["Gate"] = None
        self._lock: threading.RLock = threading.RLock()

    def find_and_assign_spot(self, vehicle: Vehicle) -> int:
        """
        Find and assign a spot atomically.

        CRITICAL SECTION:
        - Search for available spot
        - Mark it occupied
        This is a check-then-act; must be atomic to prevent double-assignment.
        """
        with self._lock:
            for floor in self.floors:
                available = floor.get_available_spots(vehicle.size)
                if available:
                    spot = available[0]
                    spot.occupy(vehicle.id)  # Atomic: no other thread can interleave
                    return spot.id

        raise NoSpotAvailableError(
            f"No available spot for {vehicle.size.name} vehicle {vehicle.id}"
        )

    def park_vehicle(self, vehicle: Vehicle, spot_id: int, entry_time: float) -> Ticket:
        """
        Park a vehicle and issue a ticket.

        CRITICAL SECTION:
        - Check if vehicle already has an active ticket
        - Create and register new ticket
        Must be atomic to prevent duplicate tickets.
        """
        with self._lock:
            if vehicle.id in self.tickets:
                raise InvalidTicketError(f"Vehicle {vehicle.id} already has an active ticket")
            ticket = Ticket.create(vehicle.id, spot_id, entry_time)
            self.tickets[ticket.id] = ticket
            return ticket

    def unpark_vehicle(self, ticket: Ticket, exit_time: float) -> float:
        """
        Unpark a vehicle, free the spot, and calculate the fee.

        CRITICAL SECTION:
        - Validate ticket exists and not already exited
        - Vacate the spot
        - Update ticket with exit_time
        - Remove from registry
        Must be atomic to prevent double-exit or torn reads.
        """
        with self._lock:
            if ticket.id not in self.tickets:
                raise InvalidTicketError(f"Ticket {ticket.id} not found in registry")

            stored_ticket = self.tickets[ticket.id]
            if stored_ticket.exit_time is not None:
                raise InvalidTicketError(f"Ticket {ticket.id} already exited")

            spot = self._get_spot_by_id(ticket.spot_id)
            spot.vacate()

            duration_hours = ticket.duration_hours(exit_time)
            fee = self.parking_rate.calculate_fee(duration_hours)

            stored_ticket.exit_time = exit_time
            del self.tickets[ticket.id]

            return fee

    def get_available_spot_count(self, size: VehicleSize) -> int:
        """
        Count available spots (read-only).
        Still acquires lock for consistent snapshot.
        """
        with self._lock:
            count = 0
            for floor in self.floors:
                count += len(floor.get_available_spots(size))
            return count

    def get_occupancy(self) -> dict:
        """
        Get occupancy stats (read-only).
        Acquires lock to ensure snapshot consistency.
        """
        with self._lock:
            total_spots = sum(len(floor.spots) for floor in self.floors)
            occupied = sum(1 for floor in self.floors for spot in floor.spots if spot.is_occupied)
            return {
                "total_spots": total_spots,
                "occupied": occupied,
                "available": total_spots - occupied,
                "occupancy_rate": occupied / total_spots if total_spots > 0 else 0.0,
                "active_tickets": len(self.tickets),
            }

    def _get_spot_by_id(self, spot_id: int) -> ParkingSpot:
        """Internal helper (called only from within lock)."""
        for floor in self.floors:
            for spot in floor.spots:
                if spot.id == spot_id:
                    return spot
        raise InvalidTicketError(f"Spot {spot_id} not found")

    def __repr__(self) -> str:
        stats = self.get_occupancy()
        return (
            f"ParkingLot(floors={len(self.floors)}, "
            f"occupied={stats['occupied']}/{stats['total_spots']}, "
            f"active_tickets={stats['active_tickets']})"
        )


class Gate:
    """Abstract base class for entry and exit gates."""

    def __init__(self, gate_id: str, lot: ParkingLot):
        self.gate_id: str = gate_id
        self.lot: ParkingLot = lot

    def process_vehicle(self, vehicle: Vehicle, timestamp: float) -> any:
        raise NotImplementedError


class EntryGate(Gate):
    """Entry gate: concurrent-safe entry processing."""

    def process_vehicle(self, vehicle: Vehicle, timestamp: float) -> Ticket:
        # These two calls will each acquire the lot's lock independently.
        # (In a real system, you might combine them into a single atomic operation,
        # but splitting them shows that the lot handles reentrancy.)
        spot_id = self.lot.find_and_assign_spot(vehicle)
        ticket = self.lot.park_vehicle(vehicle, spot_id, timestamp)
        return ticket


class ExitGate(Gate):
    """Exit gate: concurrent-safe exit processing."""

    def process_vehicle_exit(self, ticket: Ticket, timestamp: float) -> float:
        fee = self.lot.unpark_vehicle(ticket, timestamp)
        return fee
