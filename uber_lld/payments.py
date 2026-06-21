"""Payment: a third-party gateway behind an interface, wrapped by a service
that adds idempotency and retries.
"""
from __future__ import annotations

import itertools
from abc import ABC, abstractmethod
from dataclasses import dataclass

from models import PaymentFailed


# ── GATEWAY INTERFACE ────────────────────────────────────────────────────────
# 🎙️ "I hide the payment vendor behind this interface so the service doesn't
#      depend on Stripe/Braintree directly — and so I can fake it in tests."
class PaymentGateway(ABC):
    @abstractmethod
    def charge(self, amount: float, currency: str, idempotency_key: str) -> bool:
        ...


class AlwaysSuccessGateway(PaymentGateway):
    def charge(self, amount: float, currency: str, idempotency_key: str) -> bool:
        return True


class ScriptedGateway(PaymentGateway):
    """Returns results from a list in order; last result repeats.

    🎙️ "This fake lets me test the retry path — fail first, succeed second —
         without a real network."
    """

    def __init__(self, results: list[bool]) -> None:
        self._results = list(results)

    def charge(self, amount: float, currency: str, idempotency_key: str) -> bool:
        if len(self._results) > 1:
            return self._results.pop(0)
        return self._results[0]


@dataclass(frozen=True)
class Payment:
    # WHY: frozen — once a charge succeeds, the record never changes.
    id: str
    trip_id: str
    amount: float
    status: str  # "SUCCESS"


# ── PAYMENT SERVICE: idempotency + retry around the raw gateway ──────────────
# ── WHY THIS CLASS ───────────────────────────────────────────────────────────
# Wraps the gateway so the orchestrator gets one safe call. The trip id is the
# idempotency key: charging the same trip twice returns the SAME payment.
class PaymentService:
    def __init__(self, gateway: PaymentGateway, max_retries: int = 3) -> None:
        self._gw = gateway
        self._max_retries = max_retries
        self._by_key: dict[str, Payment] = {}
        self._counter = itertools.count(1)

    def charge_for_trip(self, trip_id: str, amount: float, currency: str = "USD") -> Payment:
        # WHY: idempotency — a network retry or a double "complete" tap must not
        #      double-charge. If we've already charged this trip, return the record.
        if trip_id in self._by_key:
            return self._by_key[trip_id]

        for _ in range(self._max_retries):
            # WHY: pass trip_id as the gateway idempotency key too, so even the
            #      vendor de-dups if our retry crossed with a slow success.
            if self._gw.charge(amount, currency, idempotency_key=trip_id):
                payment = Payment(
                    id=f"pay-{next(self._counter)}",
                    trip_id=trip_id,
                    amount=amount,
                    status="SUCCESS",
                )
                self._by_key[trip_id] = payment
                return payment
        # ⚠️ FOLLOW-UP: "What if it never succeeds?" → raise a typed error; the
        #    caller leaves the trip IN_PROGRESS so it can be retried — never lost.
        raise PaymentFailed(f"payment failed for trip {trip_id} after {self._max_retries} tries")
