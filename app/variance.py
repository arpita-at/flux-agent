"""Deterministic variance engine. No model is called here.

Three things this module does, all of them arithmetic:

1. Join actuals to budget and prior period by cost centre and account.
2. Decide what is material, by a rule you can read and test.
3. Decompose a variance into rate, volume and the joint effect.

The decomposition is the classic price-volume split:

    variance    = P1*Q1 - P0*Q0
    rate        = (P1 - P0) * Q0
    volume      = (Q1 - Q0) * P0
    joint       = (P1 - P0) * (Q1 - Q0)

Those three terms sum to the variance exactly. tests/test_variance.py asserts it.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable


@dataclass(frozen=True)
class Materiality:
    """What counts as worth explaining.

    A line is flagged when it is both big enough in absolute terms and big enough
    in relative terms, or when it is over the ceiling regardless of percentage.

    The `and` matters. With `or`, a cost centre that budgeted 500 and spent 2,000
    lands in the pack every month at 300% and tells nobody anything.
    """

    floor: float = 25_000.0      # absolute currency units
    pct: float = 0.10            # 10% of budget
    ceiling: float = 500_000.0   # always explain, whatever the percentage

    def flags(self, variance: float, budget: float) -> bool:
        a = abs(variance)
        if a >= self.ceiling:
            return True
        if budget == 0:
            return a >= self.floor
        return a >= self.floor and abs(variance / budget) >= self.pct


@dataclass(frozen=True)
class Line:
    cost_centre: str
    account: str
    actual: float
    budget: float
    prior: float

    @property
    def variance(self) -> float:
        return self.actual - self.budget

    @property
    def pct(self) -> float | None:
        return None if self.budget == 0 else self.variance / self.budget

    @property
    def direction(self) -> str:
        if self.variance > 0:
            return "over"
        if self.variance < 0:
            return "under"
        return "on"

    @property
    def movement(self) -> float:
        """Against the prior period, not the budget. A different question."""
        return self.actual - self.prior


@dataclass(frozen=True)
class Decomposition:
    rate: float
    volume: float
    joint: float

    @property
    def total(self) -> float:
        return self.rate + self.volume + self.joint

    @property
    def driver(self) -> str:
        """The single largest term. What you lead the sentence with."""
        return max(
            (("rate", self.rate), ("volume", self.volume), ("joint", self.joint)),
            key=lambda kv: abs(kv[1]),
        )[0]


def decompose(p0: float, q0: float, p1: float, q1: float) -> Decomposition:
    """Split a spend movement into rate, volume and the joint effect.

    p is unit price or rate, q is quantity or headcount or volume. Pass whatever
    pair actually drives the line; the arithmetic does not care what you call it.
    """
    return Decomposition(
        rate=(p1 - p0) * q0,
        volume=(q1 - q0) * p0,
        joint=(p1 - p0) * (q1 - q0),
    )


def flagged(lines: Iterable[Line], rule: Materiality | None = None) -> list[Line]:
    """The lines that need a sentence written about them, largest first."""
    rule = rule or Materiality()
    hits = [l for l in lines if rule.flags(l.variance, l.budget)]
    return sorted(hits, key=lambda l: abs(l.variance), reverse=True)


def summary(lines: list[Line], flags: list[Line]) -> dict:
    total_var = sum(l.variance for l in lines)
    explained = sum(l.variance for l in flags)
    return {
        "lines": len(lines),
        "flagged": len(flags),
        "total_variance": round(total_var, 2),
        "variance_explained": round(explained, 2),
        # How much of the movement the pack actually accounts for. Under ~80% means
        # the materiality rule is set too loose to be useful.
        "coverage": round(abs(explained) / abs(total_var), 4) if total_var else 1.0,
    }


def as_dict(line: Line) -> dict:
    d = asdict(line)
    d.update(variance=round(line.variance, 2), pct=line.pct, direction=line.direction,
             movement=round(line.movement, 2))
    return d
