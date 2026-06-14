import json
import heapq
from collections import defaultdict

# Sentinel timestamps so a missing time never wins/loses incorrectly.
_MIN_TS = ""            # sorts before any real ISO string
_MAX_TS = "9999"        # sorts after any real ISO string


def top_k_frequent_errors(path, k=10, recent_first=True):
    counts = defaultdict(int)
    latest = defaultdict(lambda: _MIN_TS)   # max timestamp seen per message
    earliest = defaultdict(lambda: _MAX_TS)  # min timestamp seen per message

    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("logType") != "error":
                continue
            msg = entry.get("message")
            if msg is None:
                continue
            ts = entry.get("time", "")
            counts[msg] += 1
            if ts > latest[msg]:
                latest[msg] = ts
            if ts < earliest[msg]:
                earliest[msg] = ts

    # Sort key: primary = count desc. secondary = timestamp.
    # recent_first: later timestamp first  -> use timestamp DESC.
    # else:         earlier timestamp first -> use timestamp ASC.
    # We make the whole key a tuple of comparables. For "string desc" we can't
    # negate a string, so we sort in two stages (stable sort), cheapest+clearest.
    items = list(counts.items())  # (msg, count)

    if recent_first:
        # tertiary stable tiebreak: message asc for full determinism
        items.sort(key=lambda mc: mc[0])                       # message asc
        items.sort(key=lambda mc: latest[mc[0]], reverse=True)  # ts desc
        items.sort(key=lambda mc: mc[1], reverse=True)          # count desc (stable)
    else:
        items.sort(key=lambda mc: mc[0])                        # message asc
        items.sort(key=lambda mc: earliest[mc[0]])              # ts asc
        items.sort(key=lambda mc: mc[1], reverse=True)          # count desc (stable)

    top = items[:k]
    ts_map = latest if recent_first else earliest
    return [(m, c, ts_map[m]) for m, c in top]


if __name__ == "__main__":
    # Two errors with the SAME count but different timestamps.
    rows = [
        {"time": "2023-04-01T10:00:00Z", "message": "Bravo", "logType": "error"},
        {"time": "2023-04-01T10:05:00Z", "message": "Bravo", "logType": "error"},
        {"time": "2023-04-01T11:00:00Z", "message": "Alpha", "logType": "error"},
        {"time": "2023-04-01T11:30:00Z", "message": "Alpha", "logType": "error"},
        {"time": "2023-04-01T09:00:00Z", "message": "Charlie", "logType": "error"},
        {"time": "2023-04-01T08:00:00Z", "message": "User login", "logType": "info"},
    ]
    with open("tie.log", "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    # Alpha and Bravo both count=2. Alpha's latest (11:30) > Bravo's latest (10:05).
    recent = top_k_frequent_errors("tie.log", k=10, recent_first=True)
    print("recent_first=True :", recent)
    assert recent == [
        ("Alpha", 2, "2023-04-01T11:30:00Z"),
        ("Bravo", 2, "2023-04-01T10:05:00Z"),
        ("Charlie", 1, "2023-04-01T09:00:00Z"),
    ], recent

    # earliest-first: Bravo first appeared 10:00 < Alpha first appeared 11:00.
    earliest = top_k_frequent_errors("tie.log", k=10, recent_first=False)
    print("recent_first=False:", earliest)
    assert earliest == [
        ("Bravo", 2, "2023-04-01T10:00:00Z"),
        ("Alpha", 2, "2023-04-01T11:00:00Z"),
        ("Charlie", 1, "2023-04-01T09:00:00Z"),
    ], earliest

    # edge: empty + k=0
    open("empty.log", "w").close()
    assert top_k_frequent_errors("empty.log") == []
    assert top_k_frequent_errors("tie.log", k=0) == []

    print("\nAll tie-break checks passed.")
