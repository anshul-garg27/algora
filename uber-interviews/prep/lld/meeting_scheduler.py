"""Reference: Meeting Room Scheduler — Uber's interval-family LLD round.
Covers all three variants Uber asked last year:
  1. canSchedule(screenings, duration, start) -> bool  (cinema variant, 2x)
  2. book(start, end) -> room id from a fixed pool, else INVALID (L5a onsite)
  3. min_rooms(intervals) -> Meeting Rooms II (phone screens)

Design notes (say out loud):
- Variant 2 is the real LLD: per-room sorted interval set + first-fit.
  Booking check = bisect into the room's sorted starts; O(log k) per room,
  O(R log k) per booking. Mention interval-tree as the scalable alternative.
- Follow-ups asked at Uber: cancellation, and "multithreaded environment".
"""
from __future__ import annotations

import bisect
import heapq
import threading

INVALID = "INVALID"


class Room:
    def __init__(self, room_id: str) -> None:
        self.id = room_id
        self.starts: list[int] = []          # sorted booking starts
        self.bookings: list[tuple[int, int]] = []  # parallel (start, end)

    def fits(self, start: int, end: int) -> bool:
        i = bisect.bisect_right(self.starts, start)
        if i < len(self.bookings) and self.bookings[i][0] < end:
            return False                      # next booking starts before we end
        if i > 0 and self.bookings[i - 1][1] > start:
            return False                      # previous booking ends after we start
        return True

    def add(self, start: int, end: int) -> None:
        i = bisect.bisect_right(self.starts, start)
        self.starts.insert(i, start)
        self.bookings.insert(i, (start, end))

    def remove(self, start: int, end: int) -> bool:
        i = bisect.bisect_left(self.starts, start)
        while i < len(self.bookings) and self.starts[i] == start:
            if self.bookings[i] == (start, end):
                self.starts.pop(i)
                self.bookings.pop(i)
                return True
            i += 1
        return False


class Scheduler:
    def __init__(self, room_ids: list[str]) -> None:
        self._rooms = [Room(r) for r in room_ids]
        self._lock = threading.Lock()   # check-then-act MUST be atomic (follow-up)

    def book(self, start: int, end: int) -> str:
        if start >= end:
            return INVALID
        with self._lock:
            for room in self._rooms:          # first-fit
                if room.fits(start, end):
                    room.add(start, end)
                    return room.id
            return INVALID

    def cancel(self, room_id: str, start: int, end: int) -> bool:
        with self._lock:
            for room in self._rooms:
                if room.id == room_id:
                    return room.remove(start, end)
            return False


def can_schedule(screenings: list[tuple[int, int]], duration: int,
                 proposed_start: int, open_t: int = 600, close_t: int = 1380) -> bool:
    """Cinema variant: can a movie of `duration` start at proposed_start?
    Hall open 10:00 (600) to 23:00 (1380), minutes from midnight."""
    end = proposed_start + duration
    if proposed_start < open_t or end > close_t:
        return False
    for s, e in screenings:
        if proposed_start < e and s < end:    # standard overlap test
            return False
    return True


def min_rooms(intervals: list[tuple[int, int]]) -> int:
    """Meeting Rooms II: min rooms to hold all meetings. O(n log n)."""
    if not intervals:
        return 0
    heap: list[int] = []                      # end times of active meetings
    for s, e in sorted(intervals):
        if heap and heap[0] <= s:
            heapq.heapreplace(heap, e)
        else:
            heapq.heappush(heap, e)
    return len(heap)


# ---------------- tests ----------------

def main() -> None:
    # variant 2 — the L5a onsite example, verbatim
    sch = Scheduler(["RoomA", "RoomB", "RoomC"])
    r1 = sch.book(2, 4); assert r1 != INVALID
    r2 = sch.book(2, 4); assert r2 != INVALID and r2 != r1
    r3 = sch.book(5, 6); assert r3 != INVALID
    r4 = sch.book(1, 5); assert r4 not in (INVALID, r1, r2)
    assert sch.book(2, 4) == INVALID          # all rooms busy in [2,4)
    assert sch.cancel(r1, 2, 4) is True
    assert sch.book(2, 4) != INVALID          # freed slot reusable
    assert sch.book(4, 5) != INVALID          # back-to-back [2,4)+[4,5) is fine

    # variant 1 — cinema
    shows = [(600, 700), (720, 800)]
    assert can_schedule(shows, 20, 700) is True     # fits the gap exactly
    assert can_schedule(shows, 30, 700) is False    # overlaps next show
    assert can_schedule(shows, 30, 1370) is False   # past closing
    assert can_schedule([], 60, 590) is False       # before opening

    # variant 3 — meeting rooms II
    assert min_rooms([(0, 30), (5, 10), (15, 20)]) == 2
    assert min_rooms([(7, 10), (2, 4)]) == 1
    assert min_rooms([]) == 0

    print("PASS")


if __name__ == "__main__":
    main()


# ---------------- FOLLOW-UP ANSWERS ----------------
# Multithreading (asked verbatim at Uber): the bug is check-then-act — two
#   threads both see RoomA free for [2,4) and both add. Fix: one scheduler
#   lock around fits+add (here), or per-room locks with try-lock ordering.
# Cancellation (asked verbatim): need booking identity; here (room,start,end),
#   production answer: booking_id -> (room, interval) map, O(1) lookup.
# Scale: first-fit over R rooms is O(R log k); for R large, keep an interval
#   tree or per-time-bucket availability index; mention, don't build.
