import threading
from bisect import insort, bisect_left


class Leaderboard:
    """Thread-safe in-memory leaderboard.

    Maintains player -> score plus a sorted index of (score, player)
    so top-N and rank queries are fast. All shared state is guarded by
    a single reentrant lock; every check-then-act is done inside it.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._scores = {}            # player_id -> current score
        # sorted ascending by (score, player); we read from the end for top-N
        self._ordered = []           # list of (score, player_id)

    # ---- internal helpers (must be called holding the lock) ----
    def _remove_entry(self, player_id, score):
        idx = bisect_left(self._ordered, (score, player_id))
        # entry must exist at idx
        if idx < len(self._ordered) and self._ordered[idx] == (score, player_id):
            self._ordered.pop(idx)

    # ---- public API ----
    def update_score(self, player_id, delta):
        """Add delta (can be negative) to a player's score. Creates the
        player if new. Returns the new score."""
        if player_id is None:
            raise ValueError("player_id cannot be None")
        if not isinstance(delta, (int, float)):
            raise ValueError("delta must be numeric")
        with self._lock:
            old = self._scores.get(player_id)
            if old is not None:
                self._remove_entry(player_id, old)
            new = (old or 0) + delta
            self._scores[player_id] = new
            insort(self._ordered, (new, player_id))
            return new

    def set_score(self, player_id, score):
        """Set absolute score (validate then mutate atomically)."""
        if player_id is None:
            raise ValueError("player_id cannot be None")
        if not isinstance(score, (int, float)):
            raise ValueError("score must be numeric")
        with self._lock:
            old = self._scores.get(player_id)
            if old is not None:
                self._remove_entry(player_id, old)
            self._scores[player_id] = score
            insort(self._ordered, (score, player_id))
            return score

    def remove_player(self, player_id):
        """Remove a player. Idempotent: returns False if not present."""
        with self._lock:
            old = self._scores.pop(player_id, None)
            if old is None:
                return False
            self._remove_entry(player_id, old)
            return True

    def top_n(self, n):
        """Return up to n (player_id, score) tuples, highest score first.
        Ties broken by player_id ascending."""
        if n < 0:
            raise ValueError("n must be >= 0")
        with self._lock:
            result = []
            if n == 0:
                return result
            for score, pid in reversed(self._ordered):
                result.append((pid, score))
                if len(result) == n:
                    break
            return result

    def get_rank(self, player_id):
        """1-based rank of a player (1 = highest). Raises if unknown."""
        with self._lock:
            if player_id not in self._scores:
                raise KeyError(f"unknown player {player_id}")
            score = self._scores[player_id]
            # rank = number of players strictly above + 1
            idx = bisect_left(self._ordered, (score, player_id))
            higher = len(self._ordered) - idx - 1
            return higher + 1

    def get_score(self, player_id):
        with self._lock:
            return self._scores.get(player_id)

    def size(self):
        with self._lock:
            return len(self._scores)


if __name__ == "__main__":
    lb = Leaderboard()

    # basic updates
    lb.update_score("alice", 50)
    lb.update_score("bob", 70)
    lb.update_score("carol", 70)   # tie with bob
    lb.update_score("dave", 30)

    assert lb.get_score("alice") == 50
    assert lb.top_n(2) == [("carol", 70), ("bob", 70)]  # tie -> player_id desc
    assert lb.get_rank("bob") == 2  # carol wins tie
    assert lb.get_rank("dave") == 4

    # incremental update re-ranks
    lb.update_score("dave", 100)   # 30 -> 130, now top
    assert lb.get_rank("dave") == 1
    assert lb.top_n(1) == [("dave", 130)]

    # negative delta
    lb.update_score("dave", -200)  # 130 -> -70
    assert lb.get_score("dave") == -70
    assert lb.get_rank("dave") == 4

    # boundary / invalid inputs
    try:
        lb.update_score(None, 5); assert False
    except ValueError: pass
    try:
        lb.get_rank("ghost"); assert False
    except KeyError: pass
    assert lb.top_n(0) == []
    assert lb.top_n(100) == lb.top_n(lb.size())  # n > size is fine

    # removal (idempotent)
    assert lb.remove_player("dave") is True
    assert lb.remove_player("dave") is False
    assert lb.get_score("dave") is None

    # concurrency stress: many threads hammering update + read
    lb2 = Leaderboard()
    PLAYERS = [f"p{i}" for i in range(20)]
    for p in PLAYERS:
        lb2.set_score(p, 0)

    def worker():
        for _ in range(1000):
            for p in PLAYERS:
                lb2.update_score(p, 1)
            lb2.top_n(5)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads: t.start()
    for t in threads: t.join()

    # each player got +1 exactly 8 threads * 1000 = 8000 times
    for p in PLAYERS:
        assert lb2.get_score(p) == 8000, (p, lb2.get_score(p))
    # internal index stays consistent with the dict
    assert len(lb2._ordered) == lb2.size() == 20

    print("All assertions passed.")
    print("Top 3:", lb2.top_n(3))
