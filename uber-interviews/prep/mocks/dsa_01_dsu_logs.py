"""
UBER DSA MOCK #1 — 45 minutes — Ride-Log Connectivity (DSU family)
====================================================================
(Uber's single most repeated DSA question: asked 3+ times in the last year
at SDE-1 and SDE-2, always with the same follow-up.)

You are given a chronologically sorted log of Uber Share rides:

    <timestamp> <UserA> shared_ride <UserB>

Each log connects UserA and UserB at that timestamp. Connectivity is
transitive. Given the total set of users appearing in the logs:

  earliest_full_connectivity(logs) -> int | -1
      Return the earliest timestamp at which ALL users belong to one
      connected component, or -1 if it never happens.

NOTE: the follow-up (don't peek — the interviewer will give it after you
finish part 1) changes the problem meaningfully. Leave time for it.

Expectations: working code, stated complexity, and you drive the
brute-force -> optimal narrative out loud in the chat.
"""

# ============== YOUR IMPLEMENTATION BELOW ==============


def earliest_full_connectivity(logs: list[str]) -> int:
    raise NotImplementedError


# ============== DEMO / ACCEPTANCE TESTS ==============

def main() -> None:
    logs1 = [
        "1 A shared_ride B",
        "3 C shared_ride D",
        "5 B shared_ride C",
    ]
    assert earliest_full_connectivity(logs1) == 5

    logs2 = [
        "1 A shared_ride B",
        "2 C shared_ride D",
    ]
    assert earliest_full_connectivity(logs2) == -1

    logs3 = ["7 X shared_ride Y"]
    assert earliest_full_connectivity(logs3) == 7

    print("PASS")


if __name__ == "__main__":
    main()
