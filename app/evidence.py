"""Evidence retrieval. Deterministic, and the reason the drafter cannot invent a cause.

The rule the whole repo rests on: the drafter is only ever shown rows that came out
of here. If nothing comes out, nothing gets drafted, and the line is returned as
`needs_evidence` instead of as a confident sentence.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Entry:
    """One supporting posting: a journal, an invoice, a PO line."""
    doc_id: str
    cost_centre: str
    account: str
    amount: float
    posted_on: str
    description: str
    source: str  # "journal" | "invoice" | "po"


def load_ledger(path: str | Path) -> list[Entry]:
    with open(path, newline="", encoding="utf-8") as fh:
        return [
            Entry(
                doc_id=r["doc_id"].strip(),
                cost_centre=r["cost_centre"].strip(),
                account=r["account"].strip(),
                amount=float(r["amount"]),
                posted_on=r["posted_on"].strip(),
                description=r["description"].strip(),
                source=r.get("source", "journal").strip(),
            )
            for r in csv.DictReader(fh)
        ]


def for_line(entries: list[Entry], cost_centre: str, account: str,
             top: int = 5) -> list[Entry]:
    """The postings behind one flagged line, biggest absolute amount first.

    Biggest first because a variance is almost always one or two large postings,
    not a drift across many small ones. If it is a drift, the caller sees small
    amounts and can say so honestly.
    """
    hits = [e for e in entries
            if e.cost_centre == cost_centre and e.account == account]
    return sorted(hits, key=lambda e: abs(e.amount), reverse=True)[:top]


def concentration(entries: list[Entry]) -> float:
    """Share of the total carried by the single largest posting, 0 to 1.

    High concentration means "one invoice did this". Low means "everything crept".
    Those need different sentences, so the drafter is told which it is.
    """
    if not entries:
        return 0.0
    total = sum(abs(e.amount) for e in entries)
    return abs(entries[0].amount) / total if total else 0.0
