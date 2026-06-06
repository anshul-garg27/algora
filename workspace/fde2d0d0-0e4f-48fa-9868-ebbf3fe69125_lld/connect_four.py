from enum import Enum
import threading


class Token(Enum):
    RED = "R"
    YELLOW = "Y"


class MoveResult(Enum):
    OK = "OK"
    WIN = "WIN"
    DRAW = "DRAW"


class InvalidMoveError(Exception):
    pass


class Player:
    def __init__(self, name, token):
        self.name = name
        self.token = token

    def __repr__(self):
        return f"Player({self.name},{self.token.value})"


class Board:
    """Owns the grid truth. Bottom row index = ROWS-1."""

    def __init__(self, rows=6, cols=7, connect=4):
        self.rows = rows
        self.cols = cols
        self.connect = connect
        # grid[r][c] holds a Token or None
        self.grid = [[None] * cols for _ in range(rows)]
        # next free row per column (from bottom). starts at rows-1
        self._next_row = [rows - 1] * cols
        self.moves_count = 0

    def is_valid_column(self, col):
        return 0 <= col < self.cols and self._next_row[col] >= 0

    def is_full(self):
        return self.moves_count == self.rows * self.cols

    def drop(self, col, token):
        """Place token in column, return (row, col) landing cell."""
        if not (0 <= col < self.cols):
            raise InvalidMoveError(f"Column {col} out of range")
        r = self._next_row[col]
        if r < 0:
            raise InvalidMoveError(f"Column {col} is full")
        self.grid[r][col] = token
        self._next_row[col] -= 1
        self.moves_count += 1
        return r, col

    def is_winning_move(self, row, col):
        """Sliding-window check on the 4 fundamental axes through (row,col)."""
        token = self.grid[row][col]
        if token is None:
            return False
        # 4 axes: horizontal, vertical, diag down-right, diag down-left
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
        need = self.connect
        for dr, dc in directions:
            count = 1
            # walk forward along axis
            count += self._count_dir(row, col, dr, dc, token)
            # walk backward along axis
            count += self._count_dir(row, col, -dr, -dc, token)
            if count >= need:
                return True
        return False

    def _count_dir(self, row, col, dr, dc, token):
        cnt = 0
        r, c = row + dr, col + dc
        while 0 <= r < self.rows and 0 <= c < self.cols and self.grid[r][c] == token:
            cnt += 1
            r += dr
            c += dc
        return cnt

    def render(self):
        out = []
        for r in range(self.rows):
            out.append(" ".join(self.grid[r][c].value if self.grid[r][c] else "."
                                 for c in range(self.cols)))
        return "\n".join(out)


class GameState(Enum):
    IN_PROGRESS = "IN_PROGRESS"
    WON = "WON"
    DRAW = "DRAW"


class Game:
    def __init__(self, players, rows=6, cols=7, connect=4):
        if len(players) != 2:
            raise ValueError("Connect Four needs exactly 2 players")
        self.board = Board(rows, cols, connect)
        self.players = players
        self.turn_idx = 0
        self.state = GameState.IN_PROGRESS
        self.winner = None
        self._lock = threading.RLock()

    @property
    def current_player(self):
        return self.players[self.turn_idx]

    def make_move(self, player, col):
        with self._lock:
            if self.state != GameState.IN_PROGRESS:
                raise InvalidMoveError("Game is already over")
            if player is not self.current_player:
                raise InvalidMoveError(
                    f"Not {player.name}'s turn; it is {self.current_player.name}'s")
            if not self.board.is_valid_column(col):
                raise InvalidMoveError(f"Invalid/full column {col}")

            row, _ = self.board.drop(col, player.token)

            if self.board.is_winning_move(row, col):
                self.state = GameState.WON
                self.winner = player
                return MoveResult.WIN
            if self.board.is_full():
                self.state = GameState.DRAW
                return MoveResult.DRAW

            self.turn_idx = 1 - self.turn_idx
            return MoveResult.OK


if __name__ == "__main__":
    red = Player("Alice", Token.RED)
    yellow = Player("Bob", Token.YELLOW)
    g = Game([red, yellow])

    # 1. Out-of-turn rejected
    try:
        g.make_move(yellow, 0)
        assert False
    except InvalidMoveError:
        pass

    # 2. Out-of-range column rejected
    try:
        g.make_move(red, 99)
        assert False
    except InvalidMoveError:
        pass

    # 3. Vertical win for Red on column 0
    # R drops col0, Y col1, R col0, Y col1, R col0, Y col1, R col0 -> win
    assert g.make_move(red, 0) == MoveResult.OK
    assert g.make_move(yellow, 1) == MoveResult.OK
    assert g.make_move(red, 0) == MoveResult.OK
    assert g.make_move(yellow, 1) == MoveResult.OK
    assert g.make_move(red, 0) == MoveResult.OK
    assert g.make_move(yellow, 1) == MoveResult.OK
    assert g.make_move(red, 0) == MoveResult.WIN
    assert g.state == GameState.WON and g.winner is red
    print(g.board.render())

    # 4. No moves after game over
    try:
        g.make_move(yellow, 2)
        assert False
    except InvalidMoveError:
        pass

    # 5. Fill a column then reject
    g2 = Game([Player("A", Token.RED), Player("B", Token.YELLOW)])
    p = g2.players
    for i in range(3):
        g2.make_move(p[0], 0)  # red
        g2.make_move(p[1], 0)  # yellow -> 6 tokens fill col 0; last is winning? check
        if g2.state != GameState.IN_PROGRESS:
            break
    # column 0 alternates R Y R Y R Y -> no 4 in a row, now full
    if g2.state == GameState.IN_PROGRESS:
        assert not g2.board.is_valid_column(0)
        try:
            g2.make_move(g2.current_player, 0)
            assert False
        except InvalidMoveError:
            pass

    # 6. Diagonal win test
    g3 = Game([Player("R", Token.RED), Player("Y", Token.YELLOW)])
    R, Y = g3.players
    # Build a down-right diagonal for R at cols 0,1,2,3
    seq = [(R,0),(Y,1),(R,1),(Y,2),(R,2),(Y,3),(R,2),(Y,3),(R,3),(Y,0),(R,3)]
    res = None
    for pl, c in seq:
        res = g3.make_move(pl, c)
    assert res == MoveResult.WIN, res
    print("Diagonal win detected:", g3.winner.name)
    print("ALL TESTS PASSED")
