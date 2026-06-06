from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from threading import RLock
from typing import Dict, List, Optional


# ---------- Domain value objects ----------
class Denomination(Enum):
    """Accepted cash denominations, value in cents to avoid float errors."""
    PENNY = 1
    NICKEL = 5
    DIME = 10
    QUARTER = 25
    DOLLAR = 100
    FIVE = 500


@dataclass(frozen=True)
class Product:
    code: str          # slot code e.g. "A1"
    name: str
    price: int         # cents


class TransactionError(Exception):
    pass


# ---------- Inventory ----------
class Inventory:
    """Tracks product stock per slot code. Guarded by the machine lock."""
    def __init__(self):
        self._stock: Dict[str, int] = {}
        self._products: Dict[str, Product] = {}

    def add_product(self, product: Product, qty: int):
        self._products[product.code] = product
        self._stock[product.code] = self._stock.get(product.code, 0) + qty

    def get(self, code: str) -> Product:
        if code not in self._products:
            raise TransactionError(f"Invalid selection: {code}")
        return self._products[code]

    def available(self, code: str) -> bool:
        return self._stock.get(code, 0) > 0

    def decrement(self, code: str):
        if self._stock.get(code, 0) <= 0:
            raise TransactionError(f"Out of stock: {code}")
        self._stock[code] -= 1

    def snapshot(self) -> Dict[str, int]:
        return dict(self._stock)


# ---------- Cash register / change strategy ----------
class CashRegister:
    """Holds coins/notes the machine can use to make change."""
    def __init__(self):
        self._float: Dict[Denomination, int] = {d: 0 for d in Denomination}

    def refill(self, d: Denomination, count: int):
        self._float[d] += count

    def deposit(self, coins: Dict[Denomination, int]):
        for d, c in coins.items():
            self._float[d] += c

    def total(self) -> int:
        return sum(d.value * c for d, c in self._float.items())

    def make_change(self, amount: int) -> Optional[Dict[Denomination, int]]:
        """Greedy change from largest denomination. Returns None if impossible.
        Does NOT mutate state unless a full solution is found."""
        if amount == 0:
            return {}
        remaining = amount
        plan: Dict[Denomination, int] = {}
        for d in sorted(Denomination, key=lambda x: -x.value):
            if remaining <= 0:
                break
            need = remaining // d.value
            use = min(need, self._float[d])
            if use > 0:
                plan[d] = use
                remaining -= use * d.value
        if remaining != 0:
            return None
        # commit
        for d, c in plan.items():
            self._float[d] -= c
        return plan


# ---------- State pattern ----------
class State(ABC):
    def __init__(self, machine: "VendingMachine"):
        self.m = machine

    @abstractmethod
    def select(self, code: str): ...
    @abstractmethod
    def insert(self, coins: Dict[Denomination, int]): ...
    @abstractmethod
    def dispense(self): ...
    @abstractmethod
    def cancel(self): ...


class IdleState(State):
    def select(self, code: str):
        product = self.m.inventory.get(code)          # validates id
        if not self.m.inventory.available(code):
            raise TransactionError(f"Out of stock: {code}")
        self.m.selected = product
        self.m.balance = 0
        self.m.set_state(self.m.has_selection)
        return product

    def insert(self, coins): raise TransactionError("Select a product first")
    def dispense(self): raise TransactionError("Nothing selected")
    def cancel(self): pass  # no-op


class HasSelectionState(State):
    def select(self, code: str):
        # allow re-selection before paying
        return self.m.idle.select(code)

    def insert(self, coins: Dict[Denomination, int]):
        for d, c in coins.items():
            if c < 0:
                raise TransactionError("Negative count")
        self.m.pending.update_with(coins)
        self.m.balance += sum(d.value * c for d, c in coins.items())
        if self.m.balance >= self.m.selected.price:
            self.m.set_state(self.m.dispensing)
            return self.m.dispense()
        return {"status": "AWAITING_MONEY", "balance": self.m.balance,
                "due": self.m.selected.price - self.m.balance}

    def dispense(self): raise TransactionError("Insufficient funds")

    def cancel(self):
        return self.m._refund_all()


class DispensingState(State):
    def select(self, code): raise TransactionError("Busy dispensing")
    def insert(self, coins): raise TransactionError("Busy dispensing")
    def cancel(self): raise TransactionError("Cannot cancel during dispense")

    def dispense(self):
        product = self.m.selected
        change_due = self.m.balance - product.price
        # tentatively deposit inserted money so it can be used for change
        self.m.register.deposit(self.m.pending.coins)
        change = self.m.register.make_change(change_due)
        if change is None:
            # roll back deposit and refund exactly what was inserted
            self.m._withdraw(self.m.pending.coins)
            refund = dict(self.m.pending.coins)
            self.m._reset()
            raise TransactionError(
                "Exact change unavailable - transaction cancelled, money returned")
        self.m.inventory.decrement(product.code)
        self.m.monitor.record_sale(product, change_due)
        result = {"product": product, "change": change}
        self.m._reset()
        return result


class MaintenanceState(State):
    def select(self, code): raise TransactionError("In maintenance")
    def insert(self, coins): raise TransactionError("In maintenance")
    def dispense(self): raise TransactionError("In maintenance")
    def cancel(self): pass


@dataclass
class Pending:
    coins: Dict[Denomination, int] = field(default_factory=dict)
    def update_with(self, coins):
        for d, c in coins.items():
            self.coins[d] = self.coins.get(d, 0) + c
    def clear(self):
        self.coins = {}


# ---------- Monitoring (Observer-ish hook) ----------
class RemoteMonitor:
    def __init__(self):
        self.sales: List[tuple] = []
    def record_sale(self, product: Product, change: int):
        self.sales.append((product.code, product.price, change))
    def report(self):
        return {"units_sold": len(self.sales),
                "revenue": sum(p for _, p, _ in self.sales)}


# ---------- The orchestrator ----------
class VendingMachine:
    def __init__(self):
        self.lock = RLock()
        self.inventory = Inventory()
        self.register = CashRegister()
        self.monitor = RemoteMonitor()
        self.pending = Pending()
        self.selected: Optional[Product] = None
        self.balance = 0
        # states
        self.idle = IdleState(self)
        self.has_selection = HasSelectionState(self)
        self.dispensing = DispensingState(self)
        self.maintenance = MaintenanceState(self)
        self._state: State = self.idle

    def set_state(self, s: State):
        self._state = s

    # public API — all serialized through one lock (check-then-act atomic)
    def select(self, code: str):
        with self.lock:
            return self._state.select(code)

    def insert(self, coins: Dict[Denomination, int]):
        with self.lock:
            return self._state.insert(coins)

    def cancel(self):
        with self.lock:
            return self._state.cancel()

    def dispense(self):
        with self.lock:
            return self._state.dispense()

    def enter_maintenance(self):
        with self.lock:
            if self._state is self.dispensing:
                raise TransactionError("Cannot service mid-dispense")
            self._refund_all()
            self.set_state(self.maintenance)

    def exit_maintenance(self):
        with self.lock:
            self.set_state(self.idle)

    # helpers (called while holding lock)
    def _refund_all(self):
        refund = dict(self.pending.coins)
        self._reset()
        return {"refund": refund}

    def _withdraw(self, coins):
        for d, c in coins.items():
            self.register._float[d] -= c

    def _reset(self):
        self.pending.clear()
        self.selected = None
        self.balance = 0
        self.set_state(self.idle)


# ---------------- DRIVER / TESTS ----------------
if __name__ == "__main__":
    m = VendingMachine()
    coke = Product("A1", "Coke", 150)
    water = Product("A2", "Water", 100)
    chips = Product("B1", "Chips", 125)
    m.inventory.add_product(coke, 2)
    m.inventory.add_product(water, 0)   # intentionally out of stock
    m.inventory.add_product(chips, 1)
    m.register.refill(Denomination.QUARTER, 10)
    m.register.refill(Denomination.DIME, 10)
    m.register.refill(Denomination.DOLLAR, 5)

    # 1. invalid selection
    try:
        m.select("Z9")
        assert False
    except TransactionError as e:
        print("invalid ->", e)

    # 2. out of stock
    try:
        m.select("A2")
        assert False
    except TransactionError as e:
        print("oos ->", e)

    # 3. happy path with change: Coke 150, pay 2 dollars -> 50 change
    m.select("A1")
    res = m.insert({Denomination.DOLLAR: 2})
    print("bought:", res["product"].name, "change:", {d.name: c for d, c in res["change"].items()})
    assert res["product"].name == "Coke"
    assert sum(d.value * c for d, c in res["change"].items()) == 50

    # 4. insufficient then top up
    m.select("B1")  # chips 125
    r = m.insert({Denomination.DOLLAR: 1})
    assert r["status"] == "AWAITING_MONEY" and r["due"] == 25
    r2 = m.insert({Denomination.QUARTER: 1})
    assert r2["product"].name == "Chips"
    print("chips ok, change:", r2["change"])

    # 5. exact change unavailable -> cancel & refund
    m2 = VendingMachine()
    odd = Product("C1", "Gum", 90)
    m2.inventory.add_product(odd, 1)
    # register empty -> cannot make 10 change for a dollar
    try:
        m2.select("C1")
        m2.insert({Denomination.DOLLAR: 1})
        assert False
    except TransactionError as e:
        print("nochange ->", e)
        # product not sold, still in stock
        assert m2.inventory.available("C1")

    # 6. cancel returns money
    m.select("A1")
    m.insert({Denomination.QUARTER: 2})
    ref = m.cancel()
    print("cancel refund:", {d.name: c for d, c in ref["refund"].items()})
    assert ref["refund"][Denomination.QUARTER] == 2

    # 7. maintenance mode blocks vending
    m.enter_maintenance()
    try:
        m.select("A1")
        assert False
    except TransactionError as e:
        print("maint ->", e)
    m.exit_maintenance()

    print("MONITOR:", m.monitor.report())
    print("ALL TESTS PASSED")
