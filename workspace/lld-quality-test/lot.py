"""
Core parking lot orchestrator and gate management.
"""

from typing import Dict, List, Optional
from datetime import datetime
from threading import RLock
import uuid

from models import (
    Vehicle, ParkingSpot, ParkingTicket, Gate, GateType,
    SpotType, SpotStatus, VehicleSize
)
from pricing import PricingStrategy


class ParkingFloor:
    """A floor containing multiple parking spots."""

    def __init__(self, floor_id: str, spots: List[ParkingSpot]) -> None:
        """
        Initialize a floor with spots.

        Args:
            floor_id: Unique identifier for this floor.
            spots: List of ParkingSpot instances on this floor.
        """
        self.floor_id = floor_id
        self.spots = spots

    def get_available_spots(self) -> List[ParkingSpot]:
        """Return all available spots on this floor."""
        return [s for s in self.spots if s.is_available()]

    @classmethod
    def create(
        cls, floor_id: str, small_count: int, medium_count: int,
        large_count: int, handicap_count: int
    ) -> "ParkingFloor":
        """
        Factory method to create a floor with the specified number of each spot type.

        Args:
            floor_id: Unique identifier for the floor.
            small_count: Number of SMALL spots.
            medium_count: Number of MEDIUM spots.
            large_count: Number of LARGE spots.
            handicap_count: Number of HANDICAP spots.

        Returns:
            A new ParkingFloor with the specified spots.
        """
        spots: List[ParkingSpot] = []
        spot_id_counter = 0

        for spot_type, count in [
            (SpotType.SMALL, small_count),
            (SpotType.MEDIUM, medium_count),
            (SpotType.LARGE, large_count),
            (SpotType.HANDICAP, handicap_count),
        ]:
            for _ in range(count):
                spot = ParkingSpot(
                    id=f"{floor_id}-{spot_type.value}-{spot_id_counter}",
                    floor_id=floor_id,
                    spot_type=spot_type,
                )
                spots.append(spot)
                spot_id_counter += 1

        return cls(floor_id, spots)


class ParkingLot:
    """
    Main orchestrator for the parking lot system.

    This class is responsible for:
    - Managing floors and spots
    - Issuing parking tickets on entry
    - Processing payments and releasing spots on exit
    - Thread-safe operations via RLock
    """

    def __init__(
        self,
        lot_id: str,
        floors: List[ParkingFloor],
        pricing_strategy: PricingStrategy,
    ) -> None:
        """
        Initialize a parking lot.

        Args:
            lot_id: Unique identifier for the lot.
            floors: List of ParkingFloor instances.
            pricing_strategy: The strategy to use for fee calculation.
        """
        self.lot_id = lot_id
        self.floors = floors
        self.pricing_strategy = pricing_strategy
        self.tickets: Dict[str, ParkingTicket] = {}
        self._lock = RLock()

    def enter(self, vehicle: Vehicle) -> Optional[ParkingTicket]:
        """
        Process a vehicle entering the lot.

        This method:
        1. Finds an available spot that fits the vehicle.
        2. Issues a parking ticket.
        3. Marks the spot as occupied.

        Args:
            vehicle: The Vehicle attempting to enter.

        Returns:
            A ParkingTicket if a spot was found, None otherwise.

        Raises:
            ValueError: If the vehicle is invalid.
        """
        if not vehicle:
            raise ValueError("Vehicle cannot be None")

        with self._lock:
            # Find an available spot
            spot = self._find_available_spot(vehicle.size)
            if not spot:
                return None  # No spot available

            # Mark the spot as occupied
            spot.mark_occupied(vehicle.vehicle_id)

            # Issue the ticket
            ticket_id = str(uuid.uuid4())
            ticket = ParkingTicket(
                ticket_id=ticket_id,
                vehicle=vehicle,
                spot=spot,
                entry_time=datetime.now(),
            )

            # Register the ticket in the lot's registry
            self.tickets[ticket_id] = ticket

            return ticket

    def exit(self, ticket: ParkingTicket) -> Optional[float]:
        """
        Process a vehicle exiting the lot.

        This method:
        1. Verifies the ticket is valid and active.
        2. Calculates the parking fee.
        3. Marks the spot as available.
        4. Records the exit in the ticket.

        Args:
            ticket: The ParkingTicket issued on entry.

        Returns:
            The fee (amount due) if the exit was successful, None if the ticket is invalid.

        Raises:
            ValueError: If the ticket is already exited or not found.
        """
        if not ticket:
            raise ValueError("Ticket cannot be None")

        with self._lock:
            # Verify the ticket exists and is active
            if ticket.ticket_id not in self.tickets:
                raise ValueError(f"Ticket {ticket.ticket_id} not found in lot registry")

            stored_ticket = self.tickets[ticket.ticket_id]
            if not stored_ticket.is_active():
                raise ValueError(f"Ticket {ticket.ticket_id} has already exited")

            # Calculate the fee
            exit_time = datetime.now()
            amount_due = self.pricing_strategy.calculate_fee(
                stored_ticket.entry_time, exit_time
            )

            # Mark the spot as available
            stored_ticket.spot.mark_available()

            # Record the exit in the ticket
            stored_ticket.exit(exit_time, amount_due)

            return amount_due

    def get_available_spots(self) -> List[ParkingSpot]:
        """
        Get a list of all available spots in the lot.

        Returns:
            A list of ParkingSpot instances that are currently available.
        """
        with self._lock:
            available = []
            for floor in self.floors:
                available.extend(floor.get_available_spots())
            return available

    def get_occupancy(self) -> Dict[str, int]:
        """
        Get occupancy statistics for the lot.

        Returns:
            A dict with 'occupied', 'available', 'total' counts.
        """
        with self._lock:
            total = 0
            occupied = 0
            for floor in self.floors:
                for spot in floor.spots:
                    total += 1
                    if spot.status == SpotStatus.OCCUPIED:
                        occupied += 1
            return {
                "occupied": occupied,
                "available": total - occupied,
                "total": total,
            }

    def _find_available_spot(self, vehicle_size: VehicleSize) -> Optional[ParkingSpot]:
        """
        Find an available spot that can fit the given vehicle.

        Searches floors in order and returns the first available spot that fits.
        (In production, this could be optimized with indexing by spot type.)

        Args:
            vehicle_size: The size of the vehicle.

        Returns:
            A ParkingSpot, or None if no spot is available.
        """
        for floor in self.floors:
            for spot in floor.spots:
                if spot.can_fit(vehicle_size):
                    return spot
        return None
