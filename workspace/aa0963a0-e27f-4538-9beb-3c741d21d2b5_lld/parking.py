import threading
import itertools
import time
from abc import ABC, abstractmethod
from enum import Enum
from datetime import datetime


# ---------------- Enums ----------------
class VehicleType(Enum):
    MOTORCYCLE = "MOTORCYCLE"
    CAR = "CAR"
    BUS = "BUS"


class SpotSize(Enum):
    SMALL = 1
    MEDIUM = 2
    LARGE = 3


# spots required (contiguous) per vehicle type, and the spot size each needs
VEHICLE_SPEC = {
    VehicleType.MOTORCYCLE: (SpotSize.SMALL, 1),
    VehicleType.CAR: (SpotSize.MEDIUM, 1),
    VehicleType.BUS: (SpotSize.LARGE, 3),  # bus needs 3 adjacent large spots
}


# ---------------- Vehicle ----------------
class Vehicle:
    def __init__(self, plate: str, vtype: VehicleType):
        if not plate:
            raise ValueError("plate required")
        self.plate = plate
        self.vtype = vtype


# ---------------- Spot ----------------
class ParkingSpot:
    def __init__(self, spot_id: str, size: SpotSize, floor: int, row: int, col: int):
        self.spot_id = spot_id
        self.size = size
        self.floor = floor
        self.row = row
        self.col = col
        self.occupied_by = None  # plate string or None

    @property
    def is_free(self):
        return self.occupied_by is None


# ---------------- Ticket ----------------
_ticket_seq = itertools.count(1)


class Ticket:
    def __init__(self, vehicle: Vehicle, spots, entry_time: float):
        self.ticket_id = f"T{next(_ticket_seq)}"
        self.vehicle = vehicle
        self.spots = spots  # list of ParkingSpot
        self.entry_time = entry_time
        self.exit_time = None
        self.fee = None
        self.paid = False


# ---------------- Fee Strategy (Strategy pattern) ----------------
class FeeStrategy(ABC):
    @abstractmethod
    def calculate(self, ticket: Ticket, exit_time: float) -> float:
        ...


class HourlyFeeStrategy(FeeStrategy):
    RATE = {VehicleType.MOTORCYCLE: 10, VehicleType.CAR: 20, VehicleType.BUS: 50}

    def calculate(self, ticket: Ticket, exit_time: float) -> float:
        import math
        hours = max(1, math.ceil((exit_time - ticket.entry_time) / 3600.0))
        return hours * self.RATE[ticket.vehicle.vtype]


# ---------------- Display Board (Observer) ----------------
class DisplayBoard:
    def update(self, counts: dict):
        self.counts = dict(counts)


# ---------------- Floor ----------------
class ParkingFloor:
    def __init__(self, floor_no: int):
        self.floor_no = floor_no
        # rows -> ordered list of spots, so adjacency is by column order
        self.rows = {}

    def add_spot(self, spot: ParkingSpot):
        self.rows.setdefault(spot.row, []).append(spot)
        self.rows[spot.row].sort(key=lambda s: s.col)

    def find_contiguous(self, size: SpotSize, n: int):
        """First-fit: n adjacent free spots of given size in some row."""
        for row in sorted(self.rows):
            spots = self.rows[row]
            run = []
            for s in spots:
                if s.is_free and s.size == size:
                    run.append(s)
                    if len(run) == n:
                        return run
                else:
                    run = []
        return None


# ---------------- Parking Lot (Orchestrator + Singleton) ----------------
class ParkingLot:
    _instance = None
    _instance_lock = threading.Lock()

    def __init__(self, fee_strategy: FeeStrategy):
        self.floors = []
        self.fee_strategy = fee_strategy
        self.active_tickets = {}      # ticket_id -> Ticket
        self.plate_to_ticket = {}     # plate -> ticket_id (prevent duplicate park)
        self.boards = []
        self._lock = threading.RLock()

    @classmethod
    def get_instance(cls, fee_strategy=None):
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = ParkingLot(fee_strategy or HourlyFeeStrategy())
            return cls._instance

    def add_floor(self, floor: ParkingFloor):
        with self._lock:
            self.floors.append(floor)

    def register_board(self, board: DisplayBoard):
        with self._lock:
            self.boards.append(board)
            board.update(self._counts())

    # ---- core ops ----
    def park(self, vehicle: Vehicle) -> Ticket:
        size, n = VEHICLE_SPEC[vehicle.vtype]
        with self._lock:
            if vehicle.plate in self.plate_to_ticket:
                raise ValueError(f"vehicle {vehicle.plate} already parked")
            for floor in self.floors:
                spots = floor.find_contiguous(size, n)
                if spots:
                    for s in spots:
                        s.occupied_by = vehicle.plate
                    ticket = Ticket(vehicle, spots, time.time())
                    self.active_tickets[ticket.ticket_id] = ticket
                    self.plate_to_ticket[vehicle.plate] = ticket.ticket_id
                    self._notify()
                    return ticket
            # explicit rejection — no silent drop
            raise RuntimeError(f"No spot available for {vehicle.vtype.value}")

    def exit_vehicle(self, ticket_id: str, exit_time: float = None) -> float:
        with self._lock:
            ticket = self.active_tickets.get(ticket_id)
            if ticket is None:
                raise ValueError(f"unknown ticket {ticket_id}")
            exit_time = exit_time if exit_time is not None else time.time()
            fee = self.fee_strategy.calculate(ticket, exit_time)
            ticket.exit_time = exit_time
            ticket.fee = fee
            return fee

    def pay_and_release(self, ticket_id: str) -> bool:
        with self._lock:
            ticket = self.active_tickets.get(ticket_id)
            if ticket is None:
                raise ValueError(f"unknown ticket {ticket_id}")
            if ticket.fee is None:
                raise RuntimeError("compute fee via exit_vehicle first")
            ticket.paid = True
            for s in ticket.spots:
                s.occupied_by = None
            del self.active_tickets[ticket_id]
            del self.plate_to_ticket[ticket.vehicle.plate]
            self._notify()
            return True

    # ---- display ----
    def _counts(self):
        counts = {vt: 0 for vt in VehicleType}
        for floor in self.floors:
            for row in floor.rows.values():
                for s in row:
                    if s.is_free:
                        for vt, (size, n) in VEHICLE_SPEC.items():
                            if s.size == size:
                                counts[vt] += 1
        # convert raw free-spot counts to "vehicles that fit" for multi-spot vehicles
        result = {}
        for vt, (size, n) in VEHICLE_SPEC.items():
            result[vt] = self._capacity_for(vt)
        return result

    def _capacity_for(self, vt: VehicleType):
        size, n = VEHICLE_SPEC[vt]
        total = 0
        for floor in self.floors:
            for row in floor.rows.values():
                run = 0
                for s in row:
                    if s.is_free and s.size == size:
                        run += 1
                    else:
                        total += run // n
                        run = 0
                total += run // n
        return total

    def _notify(self):
        counts = self._counts()
        for b in self.boards:
            b.update(counts)


# ---------------- Demo / tests ----------------
def build_lot():
    lot = ParkingLot(HourlyFeeStrategy())
    f0 = ParkingFloor(0)
    # row 0: 2 small, row 1: 2 medium, row 2: 4 large (for bus needing 3 adjacent)
    f0.add_spot(ParkingSpot("0-0-0", SpotSize.SMALL, 0, 0, 0))
    f0.add_spot(ParkingSpot("0-0-1", SpotSize.SMALL, 0, 0, 1))
    f0.add_spot(ParkingSpot("0-1-0", SpotSize.MEDIUM, 0, 1, 0))
    f0.add_spot(ParkingSpot("0-1-1", SpotSize.MEDIUM, 0, 1, 1))
    for c in range(4):
        f0.add_spot(ParkingSpot(f"0-2-{c}", SpotSize.LARGE, 0, 2, c))
    lot.add_floor(f0)
    return lot


if __name__ == "__main__":
    lot = build_lot()
    board = DisplayBoard()
    lot.register_board(board)
    print("initial capacity:", {k.value: v for k, v in board.counts.items()})

    # 1. normal car park
    t_car = lot.park(Vehicle("CAR1", VehicleType.CAR))
    assert len(t_car.spots) == 1 and t_car.spots[0].size == SpotSize.MEDIUM

    # 2. duplicate park rejected
    try:
        lot.park(Vehicle("CAR1", VehicleType.CAR))
        assert False
    except ValueError as e:
        print("duplicate rejected:", e)

    # 3. bus needs 3 adjacent large spots
    t_bus = lot.park(Vehicle("BUS1", VehicleType.BUS))
    assert len(t_bus.spots) == 3
    print("bus capacity now:", board.counts[VehicleType.BUS])  # 4 large -> only 1 run of 3 left=0

    # 4. exhaustion: second bus needs 3 adjacent but only 1 large left
    try:
        lot.park(Vehicle("BUS2", VehicleType.BUS))
        assert False
    except RuntimeError as e:
        print("no spot rejected:", e)

    # 5. unknown ticket on exit
    try:
        lot.exit_vehicle("NOPE")
        assert False
    except ValueError as e:
        print("unknown ticket rejected:", e)

    # 6. fee + release (simulate 2h stay)
    fee = lot.exit_vehicle(t_car.ticket_id, exit_time=t_car.entry_time + 2*3600)
    assert fee == 40, fee
    print("car 2h fee:", fee)
    assert lot.pay_and_release(t_car.ticket_id)

    # spot freed -> car capacity back
    print("after release capacity:", {k.value: v for k, v in board.counts.items()})

    # 7. concurrency: many threads compete for the 2 small motorcycle spots
    lot2 = build_lot()
    results = {"ok": 0, "rej": 0}
    rlock = threading.Lock()
    def worker(i):
        try:
            lot2.park(Vehicle(f"M{i}", VehicleType.MOTORCYCLE))
            with rlock: results["ok"] += 1
        except RuntimeError:
            with rlock: results["rej"] += 1
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert results["ok"] == 2, results  # only 2 small spots
    print("concurrency: parked=%d rejected=%d (exactly 2 spots)" % (results["ok"], results["rej"]))

    print("ALL ASSERTIONS PASSED")
