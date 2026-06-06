import threading
from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass, field


# ---------- Domain ----------
class Coin(Enum):
    # value in cents
    PENNY = 1
    NICKEL = 5
    DIME = 10
    QUARTER = 25
    DOLLAR = 100
    FIVE = 500


@dataclass
class Product:
    code: str
    name: str
    price: int  # cents


class TxnError(Exception):
    pass


# ---------- Change-making Strategy ----------
class ChangeStrategy(ABC):
    @abstractmethod
    def make_change(self, amount: int, bank: dict) -> dict:
        """Return {Coin: count} summing to amount using available bank, or raise TxnError."""


class GreedyChangeStrategy(ChangeStrategy):
    def make_change(self, amount: int, bank: dict) -> dict:
        result = {}
        remaining = amount
        for coin in sorted(bank.keys(), key=lambda c: c.value, reverse=True):
            if remaining <= 0:
                break
            use = min(remaining // coin.value, bank[coin])
            if use > 0:
                result[coin] = use
                remaining -= use * coin.value
        if remaining != 0:
            raise TxnError("Exact change unavailable")
        return result


# ---------- Inventory ----------
class Inventory:
    def __init__(self):
        self._products = {}          # code -> Product
        self._qty = {}               # code -> int

    def add_product(self, product: Product, qty: int):
        self._products[product.code] = product
        self._qty[product.code] = self._qty.get(product.code, 0) + qty

    def get(self, code: str) -> Product:
        if code not in self._products:
            raise TxnError(f"Invalid selection: {code}")
        return self._products[code]

    def available(self, code: str) -> bool:
        return self._qty.get(code, 0) > 0

    def dispense(self, code: str):
        if self._qty.get(code, 0) <= 0:
            raise TxnError(f"Out of stock: {code}")
        self._qty[code] -= 1

    def snapshot(self):
        return {c: self._qty[c] for c in self._qty}


# ---------- Coin bank ----------
class CoinBank:
    def __init__(self):
        self._bank = {c: 0 for c in Coin}

    def add(self, coin: Coin, count: int):
        self._bank[coin] += count

    def add_all(self, coins: dict):
        for c, n in coins.items():
            self._bank[c] += n

    def remove_all(self, coins: dict):
        for c, n in coins.items():
            self._bank[c] -= n

    def view(self):
        return dict(self._bank)


# ---------- State pattern ----------
class State(ABC):
    def __init__(self, machine):
        self.m = machine

    def select(self, code): raise TxnError(f"select not allowed in {self.name}")
    def insert(self, coin): raise TxnError(f"insert not allowed in {self.name}")
    def dispense(self): raise TxnError(f"dispense not allowed in {self.name}")
    def cancel(self): raise TxnError(f"cancel not allowed in {self.name}")

    @property
    def name(self): return type(self).__name__


class IdleState(State):
    def select(self, code):
        product = self.m.inventory.get(code)           # validates id
        if not self.m.inventory.available(code):
            raise TxnError(f"Out of stock: {code}")
        self.m.selected = product
        self.m.set_state(self.m.has_selection)
        return f"Selected {product.name} (${product.price/100:.2f})"


class HasSelectionState(State):
    def insert(self, coin):
        self.m.balance += coin.value
        self.m.pending_coins[coin] = self.m.pending_coins.get(coin, 0) + 1
        if self.m.balance >= self.m.selected.price:
            self.m.set_state(self.m.dispensing)
            return self.m.state.dispense()
        return f"Balance ${self.m.balance/100:.2f}, need ${self.m.selected.price/100:.2f}"

    def cancel(self):
        return self.m._refund_and_reset("Cancelled by user")


class DispensingState(State):
    def dispense(self):
        change_due = self.m.balance - self.m.selected.price
        # commit pending coins into bank so they can be used for change
        self.m.coin_bank.add_all(self.m.pending_coins)
        try:
            change = self.m.change_strategy.make_change(change_due, self.m.coin_bank.view()) if change_due else {}
        except TxnError:
            # roll back: take coins back out, refund originals
            self.m.coin_bank.remove_all(self.m.pending_coins)
            return self.m._refund_and_reset("Exact change unavailable")
        self.m.coin_bank.remove_all(change)
        self.m.inventory.dispense(self.m.selected.code)
        product = self.m.selected
        self.m.monitor.on_sale(product, self.m.selected.price)
        self.m._reset()
        return {"product": product.name, "change": change}


class MaintenanceState(State):
    pass  # no customer ops allowed; restock/refill happen via machine methods


# ---------- Remote monitor (Observer-ish) ----------
class Monitor:
    def __init__(self):
        self.sales = []
    def on_sale(self, product, amount):
        self.sales.append((product.code, amount))
    def report(self):
        return {"count": len(self.sales), "revenue": sum(a for _, a in self.sales)}


# ---------- The machine (orchestrator) ----------
class VendingMachine:
    def __init__(self, change_strategy: ChangeStrategy = None):
        self.inventory = Inventory()
        self.coin_bank = CoinBank()
        self.change_strategy = change_strategy or GreedyChangeStrategy()
        self.monitor = Monitor()
        self._lock = threading.RLock()

        self.idle = IdleState(self)
        self.has_selection = HasSelectionState(self)
        self.dispensing = DispensingState(self)
        self.maintenance = MaintenanceState(self)
        self.state = self.idle

        self.selected = None
        self.balance = 0
        self.pending_coins = {}

    def set_state(self, s): self.state = s

    def _reset(self):
        self.selected = None
        self.balance = 0
        self.pending_coins = {}
        self.set_state(self.idle)

    def _refund_and_reset(self, reason):
        refund = dict(self.pending_coins)
        self._reset()
        return {"refunded": refund, "reason": reason}

    # public API (all guarded + atomic check-then-act)
    def select(self, code):
        with self._lock:
            return self.state.select(code)

    def insert(self, coin):
        with self._lock:
            return self.state.insert(coin)

    def cancel(self):
        with self._lock:
            return self.state.cancel()

    # maintenance ops
    def enter_maintenance(self):
        with self._lock:
            if self.balance:
                self._refund_and_reset("maintenance")
            self.set_state(self.maintenance)

    def exit_maintenance(self):
        with self._lock:
            self.set_state(self.idle)

    def restock(self, product, qty):
        with self._lock:
            if self.state is not self.maintenance:
                raise TxnError("Restock only in maintenance")
            self.inventory.add_product(product, qty)

    def refill_change(self, coins):
        with self._lock:
            if self.state is not self.maintenance:
                raise TxnError("Refill only in maintenance")
            self.coin_bank.add_all(coins)


# ---------- Driver / tests ----------
if __name__ == "__main__":
    m = VendingMachine()
    m.enter_maintenance()
    m.restock(Product("A1", "Coke", 150), 2)
    m.restock(Product("A2", "Water", 100), 1)
    m.refill_change({Coin.QUARTER: 10, Coin.DOLLAR: 5, Coin.DIME: 10})
    m.exit_maintenance()

    # 1. invalid selection
    try:
        m.select("Z9"); assert False
    except TxnError as e:
        print("invalid ->", e)

    # 2. happy path with change: Coke 150, pay 2 dollars -> 50 change
    print(m.select("A1"))
    print(m.insert(Coin.DOLLAR))
    res = m.insert(Coin.DOLLAR)
    print("buy ->", res)
    assert res["product"] == "Coke"
    assert res["change"] == {Coin.QUARTER: 2}

    # 3. cancel returns money
    print(m.select("A2"))
    print(m.insert(Coin.QUARTER))
    ref = m.cancel()
    print("cancel ->", ref)
    assert ref["refunded"] == {Coin.QUARTER: 1}

    # 4. out of stock: buy last water then water again
    m.select("A2"); m.insert(Coin.DOLLAR)
    try:
        m.select("A2"); assert False
    except TxnError as e:
        print("oos ->", e)

    # 5. exact-change-unavailable -> full refund
    m2 = VendingMachine()
    m2.enter_maintenance()
    m2.restock(Product("B1", "Gum", 90), 1)  # no coins in bank
    m2.exit_maintenance()
    m2.select("B1")
    out = m2.insert(Coin.DOLLAR)  # pays 100, needs 10 change, bank empty
    print("nochange ->", out)
    assert out["reason"] == "Exact change unavailable"
    assert out["refunded"] == {Coin.DOLLAR: 1}

    # 6. concurrency: 20 threads buying from 5 stock, only 5 succeed
    m3 = VendingMachine()
    m3.enter_maintenance()
    m3.restock(Product("C1", "Chips", 100), 5)
    m3.refill_change({})
    m3.exit_maintenance()
    successes = []
    def buy():
        try:
            m3.select("C1")
            r = m3.insert(Coin.DOLLAR)
            if isinstance(r, dict) and r.get("product"):
                successes.append(1)
            else:
                m3.cancel()
        except TxnError:
            pass
    ts = [threading.Thread(target=buy) for _ in range(20)]
    for t in ts: t.start()
    for t in ts: t.join()
    print("concurrent successes:", sum(successes))
    assert sum(successes) <= 5

    print("monitor:", m.monitor.report())
    print("ALL ASSERTIONS PASSED")
