"""Wires the four stages together. This file is the diagram in the LinkedIn post."""
from __future__ import annotations

import csv
import os
from pathlib import Path

from .evidence import Entry, for_line, load_ledger
from .explain import draft
from .variance import Line, Materiality, decompose, flagged, summary


def load_lines(actuals: str | Path, budget: str | Path, prior: str | Path) -> list[Line]:
    def index(path):
        with open(path, newline="", encoding="utf-8") as fh:
            return {(r["cost_centre"].strip(), r["account"].strip()): float(r["amount"])
                    for r in csv.DictReader(fh)}
    a, b, p = index(actuals), index(budget), index(prior)
    keys = sorted(set(a) | set(b) | set(p))
    return [Line(cost_centre=cc, account=ac, actual=a.get((cc, ac), 0.0),
                 budget=b.get((cc, ac), 0.0), prior=p.get((cc, ac), 0.0))
            for cc, ac in keys]


def run(lines: list[Line], ledger: list[Entry], rule: Materiality | None = None,
        drivers: dict[tuple[str, str], tuple[float, float, float, float]] | None = None) -> dict:
    """Stage 1 rules, stage 2 rules, stage 3 model, stage 4 is a human, elsewhere.

    `drivers` is optional (p0, q0, p1, q1) per line. Supply it and the line gets a
    rate/volume split. Leave it out and the drafter simply does not claim a driver.
    """
    flags = flagged(lines, rule)
    drivers = drivers or {}
    out = []
    # Hard cap on model calls per run. Past this the largest variances are still
    # drafted by Claude and the tail falls back to deterministic sentences, so a
    # pathological upload costs a bounded amount instead of an open-ended one.
    budget_calls = int(os.environ.get("FLUX_MAX_DRAFTS", 25))
    for i, line in enumerate(flags):
        ev = for_line(ledger, line.cost_centre, line.account)
        key = (line.cost_centre, line.account)
        dec = decompose(*drivers[key]) if key in drivers else None
        text, cites, gap, by = draft(line, dec, ev, allow_model=i < budget_calls)
        out.append({
            "cost_centre": line.cost_centre, "account": line.account,
            "actual": round(line.actual, 2), "budget": round(line.budget, 2),
            "variance": round(line.variance, 2), "pct": line.pct,
            "direction": line.direction, "driver": dec.driver if dec else None,
            "text": text, "cites": cites, "needs_evidence": gap, "drafted_by": by,
        })
    return {"summary": summary(lines, flags), "commentary": out,
            "skipped": len(lines) - len(flags)}
