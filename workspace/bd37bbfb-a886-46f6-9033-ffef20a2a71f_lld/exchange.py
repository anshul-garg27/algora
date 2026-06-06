import threading
import time
import itertools
from enum import Enum
from dataclasses import dataclass, field
from collections import deque
from abc import ABC, abstractmethod
from typing import Optional, List, Dict


# ---------------- Enums ----------------
class OrderType(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(Enum):
    ACCEPTED = "ACCEPTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


# ---------------- Domain entities ----------------
@dataclass
class User:
    user_id: str
    name: str
    phone: str
    email: str


@dataclass
class Order:
    order_id: str
    user_id: str
    order_type: OrderType
    symbol: str
    quantity: int
    price: float
    timestamp: float = field(default_factory=time.time)
    status: OrderStatus = OrderStatus.ACCEPTED
    remaining: int = 0
    expiry_at: Optional[float] = None  # epoch seconds, optional

    def __post_init__(self):
        if self.remaining == 0:
            self.remaining = self.quantity

    def is_open(self) -> bool:
        return self.status in (OrderStatus.ACCEPTED, OrderStatus.PARTIALLY_FILLED)


@dataclass
class Trade:
    trade_id: str
    trade_type: OrderType        # taker side that triggered the trade
    buyer_order_id: str
    seller_order_id: str
    symbol: str
    quantity: int
    price: float
    timestamp: float = field(default_factory=time.time)


# ---------------- Repository abstraction (pluggable persistence) ----------------
class OrderRepository(ABC):
    @abstractmethod
    def save(self, order: Order): ...
    @abstractmethod
    def get(self, order_id: str) -> Optional[Order]: ...


class TradeRepository(ABC):
    @abstractmethod
    def save(self, trade: Trade): ...
    @abstractmethod
    def all(self) -> List[Trade]: ...


class InMemoryOrderRepository(OrderRepository):
    def __init__(self):
        self._orders: Dict[str, Order] = {}
        self._lock = threading.Lock()

    def save(self, order: Order):
        with self._lock:
            self._orders[order.order_id] = order

    def get(self, order_id: str) -> Optional[Order]:
        with self._lock:
            return self._orders.get(order_id)


class InMemoryTradeRepository(TradeRepository):
    def __init__(self):
        self._trades: List[Trade] = []
        self._lock = threading.Lock()

    def save(self, trade: Trade):
        with self._lock:
            self._trades.append(trade)

    def all(self) -> List[Trade]:
        with self._lock:
            return list(self._trades)


# ---------------- ID generation (thread-safe) ----------------
class IdGenerator:
    def __init__(self, prefix: str):
        self._prefix = prefix
        self._counter = itertools.count(1)

    def next(self) -> str:
        return f"{self._prefix}-{next(self._counter)}"


# ---------------- OrderBook per symbol ----------------
class OrderBook:
    """Holds open buy and sell orders for ONE symbol. Guarded by its own lock."""

    def __init__(self, symbol: str, trade_repo: TradeRepository, trade_id_gen: IdGenerator):
        self.symbol = symbol
        self._buys: deque[Order] = deque()   # oldest first
        self._sells: deque[Order] = deque()
        self._lock = threading.RLock()
        self._trade_repo = trade_repo
        self._trade_id_gen = trade_id_gen

    def add_and_match(self, order: Order) -> List[Trade]:
        with self._lock:
            book = self._sells if order.order_type == OrderType.BUY else self._buys
            trades = self._match(order, book)
            if order.remaining > 0 and order.is_open():
                (self._buys if order.order_type == OrderType.BUY else self._sells).append(order)
            return trades

    def _match(self, taker: Order, book: deque) -> List[Trade]:
        trades: List[Trade] = []
        # oldest-first: scan from the left, skip dead orders
        i = 0
        while taker.remaining > 0 and i < len(book):
            maker = book[i]
            if not maker.is_open():
                i += 1
                continue
            # rule: trade only when prices are EQUAL
            if maker.price != taker.price:
                i += 1
                continue
            qty = min(taker.remaining, maker.remaining)
            buyer = taker if taker.order_type == OrderType.BUY else maker
            seller = maker if taker.order_type == OrderType.BUY else taker
            trade = Trade(
                trade_id=self._trade_id_gen.next(),
                trade_type=taker.order_type,
                buyer_order_id=buyer.order_id,
                seller_order_id=seller.order_id,
                symbol=self.symbol,
                quantity=qty,
                price=maker.price,
            )
            taker.remaining -= qty
            maker.remaining -= qty
            self._update_filled_status(maker)
            self._trade_repo.save(trade)
            trades.append(trade)
            if maker.remaining == 0:
                i += 1
        self._update_filled_status(taker)
        self._compact()
        return trades

    @staticmethod
    def _update_filled_status(order: Order):
        if order.remaining == 0:
            order.status = OrderStatus.FILLED
        elif order.remaining < order.quantity:
            order.status = OrderStatus.PARTIALLY_FILLED

    def _compact(self):
        self._buys = deque(o for o in self._buys if o.is_open() and o.remaining > 0)
        self._sells = deque(o for o in self._sells if o.is_open() and o.remaining > 0)

    def remove(self, order: Order) -> bool:
        with self._lock:
            for book in (self._buys, self._sells):
                if order in book:
                    book.remove(order)
                    return True
            return False

    def expire_due(self, now: float) -> List[Order]:
        expired = []
        with self._lock:
            for book in (self._buys, self._sells):
                for o in list(book):
                    if o.expiry_at is not None and o.expiry_at <= now and o.is_open():
                        o.status = OrderStatus.EXPIRED
                        book.remove(o)
                        expired.append(o)
            return expired


# ---------------- Exchange (orchestrator / service) ----------------
class OrderNotFoundError(Exception): ...
class InvalidOrderError(Exception): ...
class UnauthorizedError(Exception): ...


class StockExchange:
    def __init__(self):
        self._users: Dict[str, User] = {}
        self._order_repo = InMemoryOrderRepository()
        self._trade_repo = InMemoryTradeRepository()
        self._order_id_gen = IdGenerator("ORD")
        self._trade_id_gen = IdGenerator("TRD")
        self._books: Dict[str, OrderBook] = {}
        self._books_lock = threading.Lock()

    def register_user(self, user: User):
        self._users[user.user_id] = user

    def _book(self, symbol: str) -> OrderBook:
        with self._books_lock:
            if symbol not in self._books:
                self._books[symbol] = OrderBook(symbol, self._trade_repo, self._trade_id_gen)
            return self._books[symbol]

    # ---- public boundary: validate everything ----
    def place_order(self, user_id, order_type: OrderType, symbol: str,
                    quantity: int, price: float, ttl_seconds: Optional[float] = None) -> Order:
        if user_id not in self._users:
            raise UnauthorizedError(f"Unknown user {user_id}")
        if quantity <= 0:
            raise InvalidOrderError("quantity must be > 0")
        if price <= 0:
            raise InvalidOrderError("price must be > 0")
        if not symbol:
            raise InvalidOrderError("symbol required")

        order = Order(
            order_id=self._order_id_gen.next(),
            user_id=user_id,
            order_type=order_type,
            symbol=symbol,
            quantity=quantity,
            price=price,
            expiry_at=(time.time() + ttl_seconds) if ttl_seconds else None,
        )
        self._order_repo.save(order)
        self._book(symbol).add_and_match(order)
        return order

    def cancel_order(self, user_id: str, order_id: str) -> Order:
        order = self._get_owned_order(user_id, order_id)
        book = self._book(order.symbol)
        with book._lock:
            if not order.is_open():
                raise InvalidOrderError(f"Cannot cancel order in status {order.status.value}")
            book.remove(order)
            order.status = OrderStatus.CANCELED
        return order

    def modify_order(self, user_id: str, order_id: str,
                     new_quantity: Optional[int] = None,
                     new_price: Optional[float] = None) -> Order:
        order = self._get_owned_order(user_id, order_id)
        if new_quantity is not None and new_quantity <= 0:
            raise InvalidOrderError("quantity must be > 0")
        if new_price is not None and new_price <= 0:
            raise InvalidOrderError("price must be > 0")
        book = self._book(order.symbol)
        with book._lock:
            if not order.is_open():
                raise InvalidOrderError(f"Cannot modify order in status {order.status.value}")
            # cancel-replace semantics: remove, update, re-match -> loses time priority
            book.remove(order)
            if new_quantity is not None:
                filled = order.quantity - order.remaining
                order.quantity = new_quantity
                order.remaining = max(0, new_quantity - filled)
            if new_price is not None:
                order.price = new_price
            order.timestamp = time.time()
            order.status = OrderStatus.ACCEPTED if order.remaining > 0 else OrderStatus.FILLED
        if order.remaining > 0:
            book.add_and_match(order)
        return order

    def get_order_status(self, user_id: str, order_id: str) -> OrderStatus:
        return self._get_owned_order(user_id, order_id).status

    def _get_owned_order(self, user_id: str, order_id: str) -> Order:
        order = self._order_repo.get(order_id)
        if order is None:
            raise OrderNotFoundError(order_id)
        if order.user_id != user_id:
            raise UnauthorizedError(f"{user_id} does not own {order_id}")
        return order

    def run_expiry_sweep(self) -> List[Order]:
        out = []
        with self._books_lock:
            books = list(self._books.values())
        now = time.time()
        for b in books:
            out.extend(b.expire_due(now))
        return out

    def all_trades(self) -> List[Trade]:
        return self._trade_repo.all()


# ---------------- Demo / tests ----------------
if __name__ == "__main__":
    ex = StockExchange()
    alice = User("U1", "Alice", "111", "a@x.com")
    bob = User("U2", "Bob", "222", "b@x.com")
    ex.register_user(alice)
    ex.register_user(bob)

    # 1. invalid input
    try:
        ex.place_order("U1", OrderType.BUY, "RELIANCE", -5, 100)
        assert False
    except InvalidOrderError:
        pass

    # unknown user
    try:
        ex.place_order("U9", OrderType.BUY, "RELIANCE", 5, 100)
        assert False
    except UnauthorizedError:
        pass

    # 2. no match -> resting in book
    o1 = ex.place_order("U1", OrderType.BUY, "RELIANCE", 10, 100.0)
    assert o1.status == OrderStatus.ACCEPTED
    assert ex.all_trades() == []

    # 3. matching sell at equal price -> trade
    o2 = ex.place_order("U2", OrderType.SELL, "RELIANCE", 4, 100.0)
    trades = ex.all_trades()
    assert len(trades) == 1
    assert trades[0].quantity == 4
    assert trades[0].buyer_order_id == o1.order_id
    assert o1.status == OrderStatus.PARTIALLY_FILLED  # 6 remaining
    assert o2.status == OrderStatus.FILLED

    # 4. oldest-first priority at same price
    oA = ex.place_order("U1", OrderType.BUY, "WIPRO", 5, 50.0)  # oldest
    oB = ex.place_order("U1", OrderType.BUY, "WIPRO", 5, 50.0)  # newer
    ex.place_order("U2", OrderType.SELL, "WIPRO", 5, 50.0)
    assert oA.status == OrderStatus.FILLED
    assert oB.status == OrderStatus.ACCEPTED

    # 5. cancel + cannot cancel filled
    oC = ex.place_order("U1", OrderType.BUY, "TCS", 3, 30.0)
    ex.cancel_order("U1", oC.order_id)
    assert oC.status == OrderStatus.CANCELED
    try:
        ex.cancel_order("U1", oC.order_id)
        assert False
    except InvalidOrderError:
        pass

    # ownership
    try:
        ex.cancel_order("U2", o1.order_id)
        assert False
    except UnauthorizedError:
        pass

    # 6. modify (cancel-replace)
    oD = ex.place_order("U1", OrderType.BUY, "INFY", 10, 70.0)
    ex.modify_order("U1", oD.order_id, new_price=80.0)
    assert oD.price == 80.0
    ex.place_order("U2", OrderType.SELL, "INFY", 10, 80.0)
    assert oD.status == OrderStatus.FILLED

    # 7. expiry
    oE = ex.place_order("U1", OrderType.BUY, "HDFC", 5, 20.0, ttl_seconds=0.05)
    time.sleep(0.1)
    expired = ex.run_expiry_sweep()
    assert oE in expired and oE.status == OrderStatus.EXPIRED

    # 8. concurrency stress: many matched pairs, no double-fill
    ex2 = StockExchange()
    ex2.register_user(alice); ex2.register_user(bob)
    N = 200
    def buyer():
        for _ in range(N):
            ex2.place_order("U1", OrderType.BUY, "X", 1, 10.0)
    def seller():
        for _ in range(N):
            ex2.place_order("U2", OrderType.SELL, "X", 1, 10.0)
    ts = [threading.Thread(target=buyer), threading.Thread(target=seller)]
    for t in ts: t.start()
    for t in ts: t.join()
    total_traded = sum(t.quantity for t in ex2.all_trades())
    assert total_traded == N, total_traded  # exactly N units crossed, none lost/duplicated
    print("All assertions passed.")
    print("Sample trades:", [(t.trade_id, t.quantity, t.price) for t in ex.all_trades()[:3]])
    print("Concurrency: total traded units =", total_traded)
