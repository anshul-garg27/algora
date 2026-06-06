from enum import Enum
from abc import ABC, abstractmethod
from threading import RLock
import heapq


class UserType(Enum):
    NORMAL = "NORMAL"
    CRITIC = "CRITIC"


# ---------- Strategy: how much a user's vote counts ----------
class WeightStrategy(ABC):
    @abstractmethod
    def weight(self) -> float:
        ...


class NormalWeight(WeightStrategy):
    def weight(self) -> float:
        return 1.0


class CriticWeight(WeightStrategy):
    def weight(self) -> float:
        return 2.0


CRITIC_PROMOTION_THRESHOLD = 3
MIN_SCORE, MAX_SCORE = 1, 5


class User:
    """A registered user. Knows its type and how many distinct movies it rated."""

    def __init__(self, user_id: str, name: str):
        self.user_id = user_id
        self.name = name
        self.user_type = UserType.NORMAL
        self._strategy: WeightStrategy = NormalWeight()
        self.rated_movie_ids = set()

    def weight(self) -> float:
        return self._strategy.weight()

    def record_rating(self, movie_id: str) -> bool:
        """Track a distinct rated movie. Returns True if this triggers promotion."""
        was_below = len(self.rated_movie_ids) < CRITIC_PROMOTION_THRESHOLD
        self.rated_movie_ids.add(movie_id)
        if (was_below and len(self.rated_movie_ids) >= CRITIC_PROMOTION_THRESHOLD
                and self.user_type == UserType.NORMAL):
            self.user_type = UserType.CRITIC
            self._strategy = CriticWeight()
            return True
        return False


class Movie:
    """Holds the raw per-user scores. Weighted average is computed on demand
    so a user's promotion to critic is reflected without rewriting history."""

    def __init__(self, movie_id: str, title: str):
        self.movie_id = movie_id
        self.title = title
        self.user_scores = {}  # user_id -> score (1..5)

    def set_score(self, user_id: str, score: int):
        self.user_scores[user_id] = score

    def weighted_average(self, users: dict) -> float:
        if not self.user_scores:
            return 0.0
        total_w = 0.0
        weighted_sum = 0.0
        for uid, score in self.user_scores.items():
            w = users[uid].weight()
            weighted_sum += score * w
            total_w += w
        return weighted_sum / total_w if total_w else 0.0


class RatingSystem:
    """Orchestrator: owns users and movies, validates every boundary,
    and guards all shared state with one reentrant lock."""

    def __init__(self):
        self._users = {}
        self._movies = {}
        self._lock = RLock()

    # ---- registration ----
    def add_user(self, user_id: str, name: str) -> User:
        with self._lock:
            if user_id in self._users:
                raise ValueError(f"User '{user_id}' already exists")
            user = User(user_id, name)
            self._users[user_id] = user
            return user

    def add_movie(self, movie_id: str, title: str) -> Movie:
        with self._lock:
            if movie_id in self._movies:
                raise ValueError(f"Movie '{movie_id}' already exists")
            movie = Movie(movie_id, title)
            self._movies[movie_id] = movie
            return movie

    # ---- core action ----
    def rate_movie(self, user_id: str, movie_id: str, score: int):
        with self._lock:
            if user_id not in self._users:
                raise KeyError(f"Unknown user '{user_id}'")
            if movie_id not in self._movies:
                raise KeyError(f"Unknown movie '{movie_id}'")
            if not isinstance(score, int) or not (MIN_SCORE <= score <= MAX_SCORE):
                raise ValueError(f"Score must be int in [{MIN_SCORE},{MAX_SCORE}]")

            movie = self._movies[movie_id]
            user = self._users[user_id]
            # replace-or-insert; record_rating dedupes by movie id
            movie.set_score(user_id, score)
            promoted = user.record_rating(movie_id)
            return promoted

    def get_movie_rating(self, movie_id: str) -> float:
        with self._lock:
            if movie_id not in self._movies:
                raise KeyError(f"Unknown movie '{movie_id}'")
            return self._movies[movie_id].weighted_average(self._users)

    def get_top_k_movies(self, k: int):
        if k < 0:
            raise ValueError("k must be non-negative")
        with self._lock:
            rated = [m for m in self._movies.values() if m.user_scores]
            scored = [(m.weighted_average(self._users), m.title, m.movie_id)
                      for m in rated]
            # highest rating first; tie-break by title for determinism
            top = heapq.nlargest(k, scored, key=lambda x: (x[0], x[1]))
            return [(mid, title, round(avg, 4)) for avg, title, mid in top]


if __name__ == "__main__":
    rs = RatingSystem()
    for i in range(1, 6):
        rs.add_user(f"u{i}", f"User{i}")
    for c in "ABCD":
        rs.add_movie(f"m{c}", f"Movie{c}")

    # --- boundary / validation ---
    try:
        rs.rate_movie("u1", "mA", 6)
        assert False
    except ValueError:
        pass
    try:
        rs.rate_movie("ux", "mA", 3)
        assert False
    except KeyError:
        pass
    try:
        rs.add_user("u1", "dup")
        assert False
    except ValueError:
        pass

    # --- normal ratings ---
    rs.rate_movie("u1", "mA", 4)
    rs.rate_movie("u2", "mA", 2)
    # weighted avg = (4+2)/2 = 3.0, both normal
    assert rs.get_movie_rating("mA") == 3.0

    # --- duplicate rating replaces, doesn't double-count ---
    rs.rate_movie("u1", "mA", 2)   # u1 changes 4 -> 2
    assert rs.get_movie_rating("mA") == 2.0   # (2+2)/2
    assert len(rs._users["u1"].rated_movie_ids) == 1  # still one distinct movie

    # --- promotion to critic on 3rd distinct movie ---
    assert rs.rate_movie("u1", "mB", 5) is False
    promoted = rs.rate_movie("u1", "mC", 5)
    assert promoted is True
    assert rs._users["u1"].user_type == UserType.CRITIC

    # u1 is now critic (weight 2). mA: u1=2(w2), u2=2(w1) -> (2*2+2)/3 = 2.0
    assert abs(rs.get_movie_rating("mA") - 2.0) < 1e-9
    # mB only u1=5 critic -> 5.0 ; mC only u1=5 -> 5.0

    # --- empty movie excluded from top-k ---
    rs.add_movie("mE", "MovieE")  # no ratings
    top = rs.get_top_k_movies(10)
    titles = [t for _, t, _ in top]
    assert "MovieE" not in titles

    # --- top k correctness ---
    top2 = rs.get_top_k_movies(2)
    assert top2[0][0] in ("mB", "mC")  # ids, both rated 5.0
    print("Top movies:")
    for mid, title, avg in rs.get_top_k_movies(5):
        print(f"  {title} ({mid}): {avg}")
    print("ALL ASSERTIONS PASSED")
