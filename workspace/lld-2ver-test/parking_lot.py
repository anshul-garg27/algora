"""The ParkingLot orchestrator: manages entry, exit, spot allocation, and ticket registry."""

from typing import Optional, Callable
from models import (
    Vehicle, VehicleSize, ParkingSpot, ParkingFloor, Ticket, ParkingRate,
    NoSpotAvailableError, InvalidTicketError
)


class ParkingLot:
    """
    The central orchestrator for the parking lot.

    Owns:
    - floors and all spots (composition)
    - ticket registry (active tickets for parked vehicles)
    - entry and exit gates (dependencies)

    Invariants:
    - len(tickets) == count of occupied spots
    - every occupied spot has an entry in tickets
    """

    def __init__(self, floors: list[ParkingFloor], hourly_rate: float = 2.0):
        """
        Args:
            floors: List of ParkingFloor objects.
            hourly_rate: Hourly parking rate in dollars.
        """
        self.floors: list[ParkingFloor] = floors
        self.tickets: dict[str, Ticket] = {}  # ticket_id -> Ticket
        self.parking_rate: ParkingRate = ParkingRate(hourly_rate)
        self.entry_gate: Optional["Gate"] = None
        self.exit_gate: Optional["Gate"] = None

    def find_and_assign_spot(self, vehicle: Vehicle) -> int:
        """
        Find an available spot suitable for the vehicle, mark it occupied,
        and return the spot ID. If no spot available, raise NoSpotAvailableError.

        This is a check-then-act operation: find an empty spot that fits,
        then immediately mark it occupied. In a concurrent system, this MUST
        be atomic (guarded by a lock in §9).
        """
        for floor in self.floors:
            available = floor.get_available_spots(vehicle.size)
            if available:
                spot = available[0]  # Take the smallest suitable spot
                spot.occupy(vehicle.id)
                return spot.id

        raise NoSpotAvailableError(
            f"No available spot for {vehicle.size.name} vehicle {vehicle.id}"
        )

    def park_vehicle(self, vehicle: Vehicle, spot_id: int, entry_time: float) -> Ticket:
        """
        Park a vehicle in a spot (after find_and_assign_spot has already marked it occupied).
        Create and register a ticket.

        Args:
            vehicle: The vehicle object.
            spot_id: The spot ID (must already be marked occupied).
            entry_time: Entry timestamp (in seconds, e.g., from time.time()).

        Returns:
            The issued Ticket.

        Raises:
            InvalidTicketError if ticket already exists for this vehicle.
        """
        if vehicle.id in self.tickets:
            raise InvalidTicketError(f"Vehicle {vehicle.id} already has an active ticket")

        ticket = Ticket.create(vehicle.id, spot_id, entry_time)
        self.tickets[ticket.id] = ticket
        return ticket

    def unpark_vehicle(self, ticket: Ticket, exit_time: float) -> float:
        """
        Remove a vehicle from its spot, free the spot, calculate and return the fee.

        Args:
            ticket: The ticket to validate and exit.
            exit_time: Exit timestamp (in seconds).

        Returns:
            The parking fee in dollars.

        Raises:
            InvalidTicketError if the ticket is not found or already exited.
        """
        if ticket.id not in self.tickets:
            raise InvalidTicketError(f"Ticket {ticket.id} not found in registry")

        stored_ticket = self.tickets[ticket.id]
        if stored_ticket.exit_time is not None:
            raise InvalidTicketError(f"Ticket {ticket.id} already exited at {stored_ticket.exit_time}")

        # Find and vacate the spot
        spot = self._get_spot_by_id(ticket.spot_id)
        spot.vacate()

        # Calculate fee
        duration_hours = ticket.duration_hours(exit_time)
        fee = self.parking_rate.calculate_fee(duration_hours)

        # Mark ticket as exited
        stored_ticket.exit_time = exit_time

        # Remove from active tickets
        del self.tickets[ticket.id]

        return fee

    def get_available_spot_count(self, size: VehicleSize) -> int:
        """Count available spots for a given vehicle size."""
        count = 0
        for floor in self.floors:
            count += len(floor.get_available_spots(size))
        return count

    def get_occupancy(self) -> dict:
        """Return current occupancy stats."""
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
        """Internal: find a spot by ID across all floors."""
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
    """
    Abstract base class for entry and exit gates.
    Template method: process_vehicle() is the entry point.
    """

    def __init__(self, gate_id: str, lot: ParkingLot):
        self.gate_id: str = gate_id
        self.lot: ParkingLot = lot

    def process_vehicle(self, vehicle: Vehicle, timestamp: float) -> any:
        """
        Process a vehicle (entry or exit). Subclasses override this.

        Args:
            vehicle: The vehicle to process.
            timestamp: Current timestamp.

        Returns:
            Result of processing (Ticket for entry, fee for exit).
        """
        raise NotImplementedError


class EntryGate(Gate):
    """
    Entry gate: receive a vehicle, find and assign a spot, issue a ticket.
    """

    def process_vehicle(self, vehicle: Vehicle, timestamp: float) -> Ticket:
        """
        Process entry:
        1. Find an available spot for the vehicle
        2. Mark it occupied
        3. Issue a ticket

        Args:
            vehicle: The incoming vehicle.
            timestamp: Entry timestamp.

        Returns:
            Ticket for the parked vehicle.

        Raises:
            NoSpotAvailableError if no suitable spot is available.
            InvalidTicketError if vehicle already has an active ticket.
        """
        # Find and assign a spot (atomic check-then-act)
        spot_id = self.lot.find_and_assign_spot(vehicle)

        # Create and register ticket
        ticket = self.lot.park_vehicle(vehicle, spot_id, timestamp)

        return ticket


class ExitGate(Gate):
    """
    Exit gate: receive a ticket, validate it, calculate fee, free the spot.
    """

    def process_vehicle_exit(self, ticket: Ticket, timestamp: float) -> float:
        """
        Process exit:
        1. Validate the ticket
        2. Calculate the fee
        3. Free the spot
        4. Remove the ticket from registry

        Args:
            ticket: The ticket to validate and exit.
            timestamp: Exit timestamp.

        Returns:
            Parking fee in dollars.

        Raises:
            InvalidTicketError if the ticket is invalid or already exited.
        """
        fee = self.lot.unpark_vehicle(ticket, timestamp)
        return fee
