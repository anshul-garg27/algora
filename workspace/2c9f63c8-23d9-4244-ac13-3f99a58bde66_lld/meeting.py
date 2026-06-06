import threading
import itertools
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class BookingStatus(Enum):
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class Interval:
    start: int  # epoch minutes (any comparable time unit)
    end: int

    def __post_init__(self):
        if self.start >= self.end:
            raise ValueError(f"Invalid interval: start {self.start} >= end {self.end}")

    def overlaps(self, other: "Interval") -> bool:
        # half-open [start, end): touching edges do NOT overlap
        return self.start < other.end and other.start < self.end


@dataclass
class Employee:
    id: str
    name: str


@dataclass
class MeetingRoom:
    id: str
    name: str
    capacity: int


@dataclass
class Booking:
    id: str
    room_id: str
    employee_id: str
    interval: Interval
    status: BookingStatus = BookingStatus.CONFIRMED


class BookingError(Exception):
    pass


class RoomSchedule:
    """Owns the truth for ONE room's confirmed bookings. Guards its own state."""

    def __init__(self, room: MeetingRoom):
        self.room = room
        self._bookings: dict[str, Booking] = {}
        self._lock = threading.RLock()

    def is_free(self, interval: Interval) -> bool:
        with self._lock:
            return not any(
                b.interval.overlaps(interval)
                for b in self._bookings.values()
                if b.status == BookingStatus.CONFIRMED
            )

    def try_reserve(self, booking: Booking) -> bool:
        # atomic check-then-act under the room lock
        with self._lock:
            if not self.is_free(booking.interval):
                return False
            self._bookings[booking.id] = booking
            return True

    def cancel(self, booking_id: str) -> Optional[Booking]:
        with self._lock:
            b = self._bookings.get(booking_id)
            if b and b.status == BookingStatus.CONFIRMED:
                b.status = BookingStatus.CANCELLED
                return b
            return None

    def list_confirmed(self) -> list[Booking]:
        with self._lock:
            return [b for b in self._bookings.values()
                    if b.status == BookingStatus.CONFIRMED]


class ReservationService:
    """Orchestrator: owns registries of rooms, employees, bookings."""

    def __init__(self):
        self._rooms: dict[str, RoomSchedule] = {}
        self._employees: dict[str, Employee] = {}
        self._bookings_index: dict[str, Booking] = {}  # global id -> booking
        self._id_gen = itertools.count(1)
        self._lock = threading.RLock()

    # --- registration ---
    def add_room(self, room: MeetingRoom):
        with self._lock:
            self._rooms[room.id] = RoomSchedule(room)

    def add_employee(self, emp: Employee):
        with self._lock:
            self._employees[emp.id] = emp

    def _new_id(self) -> str:
        return f"BK-{next(self._id_gen)}"

    # --- core operations ---
    def get_available_rooms(self, start: int, end: int) -> list[MeetingRoom]:
        interval = Interval(start, end)  # validates range
        with self._lock:
            schedules = list(self._rooms.values())
        return [s.room for s in schedules if s.is_free(interval)]

    def book_room(self, employee_id: str, room_id: str, start: int, end: int) -> Booking:
        interval = Interval(start, end)  # validates range, raises on invalid
        with self._lock:
            if employee_id not in self._employees:
                raise BookingError(f"Unknown employee {employee_id}")
            schedule = self._rooms.get(room_id)
            if schedule is None:
                raise BookingError(f"Unknown room {room_id}")
            booking = Booking(self._new_id(), room_id, employee_id, interval)

        # reserve atomically on the room itself
        if not schedule.try_reserve(booking):
            raise BookingError(
                f"Room {room_id} not available for {start}-{end} (overlap)")
        with self._lock:
            self._bookings_index[booking.id] = booking
        return booking

    def cancel_booking(self, booking_id: str) -> None:
        with self._lock:
            booking = self._bookings_index.get(booking_id)
            schedule = self._rooms.get(booking.room_id) if booking else None
        if booking is None:
            raise BookingError(f"Unknown booking {booking_id}")
        if schedule.cancel(booking_id) is None:
            raise BookingError(f"Booking {booking_id} already cancelled")

    def list_bookings_for_room(self, room_id: str) -> list[Booking]:
        with self._lock:
            schedule = self._rooms.get(room_id)
        if schedule is None:
            raise BookingError(f"Unknown room {room_id}")
        return schedule.list_confirmed()

    def list_bookings_for_employee(self, employee_id: str) -> list[Booking]:
        with self._lock:
            return [b for b in self._bookings_index.values()
                    if b.employee_id == employee_id
                    and b.status == BookingStatus.CONFIRMED]


if __name__ == "__main__":
    svc = ReservationService()
    svc.add_room(MeetingRoom("A", "Room A", 10))
    svc.add_room(MeetingRoom("B", "Room B", 6))
    svc.add_employee(Employee("X", "User X"))
    svc.add_employee(Employee("Y", "User Y"))
    svc.add_employee(Employee("Z", "User Z"))

    # times in minutes; 600=10:00, 660=11:00, 630=10:30, 690=11:30
    b1 = svc.book_room("Z", "A", 600, 660)
    print("Booked", b1.id)

    # 1. overlap -> fail
    try:
        svc.book_room("X", "A", 630, 690)
        assert False, "should have failed"
    except BookingError as e:
        print("Overlap rejected:", e)

    # 2. different room -> success
    b2 = svc.book_room("Y", "B", 630, 690)
    print("Booked", b2.id)

    # 3. edge touch (no overlap): 660-720 right after 600-660
    b3 = svc.book_room("X", "A", 660, 720)
    print("Touching booking ok:", b3.id)

    # 4. invalid range
    try:
        svc.book_room("X", "A", 700, 700)
        assert False
    except ValueError as e:
        print("Invalid range rejected:", e)

    # 5. unknown room / employee
    try:
        svc.book_room("X", "ZZ", 800, 900)
        assert False
    except BookingError as e:
        print("Unknown room rejected:", e)

    # 6. availability query
    avail = svc.get_available_rooms(630, 690)
    print("Available at 630-690:", [r.id for r in avail])  # only A is busy->B busy too; expect none? A busy, B busy
    # A busy(630-690 overlaps 600-660? yes), B busy -> expect empty
    assert avail == []

    avail2 = svc.get_available_rooms(900, 960)
    assert {r.id for r in avail2} == {"A", "B"}

    # 7. cancel then rebook
    svc.cancel_booking(b1.id)
    print("Cancelled", b1.id)
    try:
        svc.cancel_booking(b1.id)
        assert False
    except BookingError as e:
        print("Double cancel rejected:", e)
    b4 = svc.book_room("Y", "A", 600, 660)  # now free again
    print("Rebooked freed slot:", b4.id)

    # 8. concurrency: many threads race for same slot, exactly one wins
    svc.add_room(MeetingRoom("C", "Room C", 4))
    results = []
    rlock = threading.Lock()
    def race():
        try:
            bk = svc.book_room("X", "C", 1000, 1060)
            with rlock:
                results.append(bk.id)
        except BookingError:
            pass
    threads = [threading.Thread(target=race) for _ in range(50)]
    for t in threads: t.start()
    for t in threads: t.join()
    print("Concurrent winners:", results)
    assert len(results) == 1, results

    # listings
    print("Room A bookings:", [b.id for b in svc.list_bookings_for_room("A")])
    print("Employee X bookings:", [b.id for b in svc.list_bookings_for_employee("X")])
    print("ALL ASSERTIONS PASSED")
