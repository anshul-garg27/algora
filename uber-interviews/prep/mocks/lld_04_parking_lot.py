"""
UBER MACHINE CODING / LLD MOCK #4 — 45 minutes — Parking Lot
==============================================================
(The classic — but it cut a real SDE-1 last year: strong DSA + behavioral,
rejected on this round. Also asked in an intern offer loop. Uber's bar:
class design AND working allocation logic, not just UML.)

Design a multi-floor parking lot:
  * Floors have rows of spots. Spot sizes: SMALL, MEDIUM, LARGE.
  * Vehicles: BIKE (fits S/M/L), CAR (fits M/L), BUS (needs 2 ADJACENT
    LARGE spots in the same row).
  * park(vehicle) -> Ticket | None   (assign FIRST suitable spot(s):
      lowest floor, then lowest row, then lowest spot index)
  * unpark(ticket_id) -> bool
  * availability(floor) -> dict like {"SMALL": 3, "MEDIUM": 2, "LARGE": 5}

Expectations:
  1. RUNNABLE — demo below must print PASS.
  2. Clean entities: Vehicle types, Spot, Floor, Lot, Ticket.
  3. The BUS adjacency requirement is the differentiator — design for it,
     don't bolt it on.
  4. Follow-ups will probe allocation strategy & concurrency.

When done (or at 45 min), say "done" to the interviewer chat.
"""

# ============== YOUR IMPLEMENTATION BELOW ==============


class ParkingLot:
    pass  # replace with your design (more classes welcome)


# ============== DEMO / ACCEPTANCE TESTS ==============

def main() -> None:
    # build(floors) -> floor spec: list of rows, row = list of sizes
    lot = ParkingLot([
        [["SMALL", "LARGE", "LARGE", "MEDIUM"],          # floor 0, row 0
         ["LARGE", "LARGE", "LARGE", "SMALL"]],          # floor 0, row 1
        [["MEDIUM", "MEDIUM"]],                          # floor 1, row 0
    ])

    t_bike = lot.park("BIKE")                  # -> floor0 row0 spot0 (SMALL)
    assert t_bike is not None
    t_car = lot.park("CAR")                    # -> floor0 row0 spot1 (LARGE first M/L)
    assert t_car is not None
    t_bus = lot.park("BUS")                    # needs 2 adjacent LARGE in a row
    assert t_bus is not None                   # row1 spots 0-1 (row0's larges: 1 taken)
    assert lot.park("BUS") is None             # no two adjacent LARGE left
    av0 = lot.availability(0)
    assert av0["LARGE"] == 1 and av0["SMALL"] == 1   # row1: L@2 free, S@3 free

    assert lot.unpark(t_bus.id) is True
    assert lot.park("BUS") is not None         # freed pair reusable
    assert lot.unpark("nope") is False

    t2 = lot.park("CAR"); t3 = lot.park("CAR")
    assert t2 is not None and t3 is not None   # mediums on floor 1 get used
    print("PASS")


if __name__ == "__main__":
    main()
