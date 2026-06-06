from typing import Optional, Dict, List
from datetime import datetime
from threading import Lock
from models import Vehicle, Ticket, SpotSize, VehicleType
from pricing import PricingStrategy, HourlyPricingStrategy


class ParkingSpot:
    """
    Represents a single parking spot.
    A spot has a size category and can be occupied by at most one vehicle.
    """

    def __init__(self, spot_id: str, level_number: int, size: SpotSize):
        self.spot_id = spot_id
        self.level_number = level_number
        self.size = size
        self.vehicle: Optional[Vehicle] = None
        self.entry_time: Optional[datetime] = None

    def park(self, vehicle: Vehicle, entry_time: datetime) -> bool:
        """
        Attempt to park a vehicle in this spot.
        Returns True if successful, False if spot is already occupied.
        """
        if self.vehicle is not None:
            return False
        # Check if vehicle size fits this spot
        if not self._fits(vehicle):
            return False
        self.vehicle = vehicle
        self.entry_time = entry_time
        return True

    def unpark(self) -> Optional[Vehicle]:
        """
        Remove the vehicle from this spot.
        Returns the vehicle if one was parked, None otherwise.
        """
        vehicle = self.vehicle
        self.vehicle = None
        self.entry_time = None
        return vehicle

    def is_available(self) -> bool:
        """Check if this spot is currently empty and available."""
        return self.vehicle is None

    def _fits(self, vehicle: Vehicle) -> bool:
        """Check if a vehicle can fit in this spot (size-based)."""
        required_size = vehicle.required_size
        # A spot fits if its size is >= required size
        size_order = [SpotSize.COMPACT, SpotSize.REGULAR, SpotSize.LARGE]
        return size_order.index(self.size) >= size_order.index(required_size)

    def __repr__(self) -> str:
        status = f"occupied by {self.vehicle.license_plate}" if self.vehicle else "empty"
        return f"Spot({self.spot_id}, {self.size.value}, {status})"


class Level:
    """
    Represents one level (floor) of the parking lot.
    A level contains multiple parking spots.
    """

    def __init__(self, level_number: int, spots: List[ParkingSpot]):
        self.level_number = level_number
        self.spots = spots

    def find_available_spot(self, required_size: SpotSize) -> Optional[ParkingSpot]:
        """
        Find the first available spot that can fit the required size.
        Returns the spot, or None if no spot is available.
        """
        size_order = [SpotSize.COMPACT, SpotSize.REGULAR, SpotSize.LARGE]
        for spot in self.spots:
            if spot.is_available():
                # Check if this spot's size is >= required size
                if size_order.index(spot.size) >= size_order.index(required_size):
                    return spot
        return None

    def get_occupancy(self) -> int:
        """Return the number of occupied spots."""
        return sum(1 for spot in self.spots if not spot.is_available())

    def __repr__(self) -> str:
        occupied = self.get_occupancy()
        total = len(self.spots)
        return f"Level {self.level_number}: {occupied}/{total} occupied"


class ParkingLot:
    """
    The main parking lot manager.
    Orchestrates entry/exit, manages all levels and spots, and issues tickets.
    """

    def __init__(self, levels: List[Level], pricing_strategy: PricingStrategy):
        self.levels = levels
        self.pricing_strategy = pricing_strategy
        self.ticket_counter = 0
        self.active_tickets: Dict[str, Ticket] = {}  # Maps ticket_id -> Ticket
        self.completed_tickets: List[Ticket] = []
        self.lock = Lock()  # Thread safety for concurrent park/unpark

    def park_vehicle(self, vehicle: Vehicle) -> Ticket:
        """
        Attempt to park a vehicle.
        Returns a Ticket if successful.
        Raises ValueError if no spot is available or vehicle is invalid.
        """
        with self.lock:
            # Find an available spot that fits the vehicle's size
            required_size = vehicle.required_size
            spot = None
            for level in self.levels:
                spot = level.find_available_spot(required_size)
                if spot:
                    break

            if spot is None:
                raise ValueError(f"No available spot for {vehicle.vehicle_type.value}")

            # Park the vehicle in the spot
            entry_time = datetime.now()
            if not spot.park(vehicle, entry_time):
                raise ValueError(f"Failed to park vehicle in spot {spot.spot_id}")

            # Create and store the ticket
            self.ticket_counter += 1
            ticket_id = f"TICKET_{self.ticket_counter:06d}"
            ticket = Ticket(
                ticket_id=ticket_id,
                vehicle=vehicle,
                spot_id=spot.spot_id,
                level_number=spot.level_number,
                entry_time=entry_time,
            )
            self.active_tickets[ticket_id] = ticket
            return ticket

    def unpark_vehicle(self, ticket_id: str) -> float:
        """
        Unpark a vehicle given its ticket ID.
        Computes the fee, clears the spot, and closes the ticket.
        Returns the fee amount.
        Raises ValueError if ticket is not found or invalid.
        """
        with self.lock:
            if ticket_id not in self.active_tickets:
                raise ValueError(f"Ticket {ticket_id} not found or already completed")

            ticket = self.active_tickets[ticket_id]
            exit_time = datetime.now()

            # Find the spot and unpark the vehicle
            spot = None
            for level in self.levels:
                for s in level.spots:
                    if s.spot_id == ticket.spot_id:
                        spot = s
                        break
                if spot:
                    break

            if spot is None or spot.vehicle is None:
                raise ValueError(f"Vehicle not found in spot {ticket.spot_id}")

            # Unpark the vehicle
            spot.unpark()

            # Calculate the fee
            fee = self.pricing_strategy.calculate_fee(ticket.entry_time, exit_time)

            # Close the ticket
            ticket.exit_time = exit_time
            ticket.fee = fee
            self.active_tickets.pop(ticket_id)
            self.completed_tickets.append(ticket)

            return fee

    def get_available_spot_count(self) -> int:
        """Return the total number of available spots."""
        return sum(
            sum(1 for spot in level.spots if spot.is_available())
            for level in self.levels
        )

    def get_occupancy(self) -> int:
        """Return the total number of occupied spots."""
        return sum(level.get_occupancy() for level in self.levels)

    def get_capacity(self) -> int:
        """Return the total number of spots in the lot."""
        return sum(len(level.spots) for level in self.levels)

    def get_occupancy_percentage(self) -> float:
        """Return occupancy as a percentage."""
        total = self.get_capacity()
        if total == 0:
            return 0.0
        return (self.get_occupancy() / total) * 100

    def __repr__(self) -> str:
        occupancy = self.get_occupancy()
        capacity = self.get_capacity()
        percentage = self.get_occupancy_percentage()
        return f"ParkingLot: {occupancy}/{capacity} occupied ({percentage:.1f}%)"
