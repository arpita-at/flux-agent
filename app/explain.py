"""The drafter. The only place a model is allowed anywhere near this pipeline.

Two implementations behind one function:

  * rules  - template sentences built from the decomposition and the evidence.
             Always available, never wrong, slightly wooden.
  * claude - a drafted sentence, given ONLY the evidence rows retrieved for that
             line. No ledger access, no tools, no numbers of its own.

Either way the output carries `cites`, the document ids it was allowed to see. A
line with no evidence is returned with needs_evidence=True and no explanation at
all. That is the control: the pipeline would rather hand back a gap than a guess.
"""
from __future__ import annotations

import json
import os

from .evidence import Entry, concentration
from .variance import Decomposition, Line

MODEL = os.environ.get("FLUX_MODEL", "claude-sonnet-5-5")

SYSTEM = """You write month-end flux commentary for a finance pack.

Rules you must follow:
- Use ONLY the evidence rows given to you. Never infer a cause they do not support.
- Never restate the variance number. The reader can already see it in the row above.
- Lead with the cause, not the amount.
- One or two sentences. A reader has thirty seconds.
- Name the driver (rate, volume or joint) only if the decomposition supports it.
- If the evidence does not explain the movement, say exactly that and stop.
- Plain English. No "due to the fact that", no em dashes.
"""


def rules_draft(line: Line, dec: Decomposition | None, ev: list[Entry]) -> str:
    """Deterministic sentence. Boring on purpose, and never wrong."""
    if not ev:
        return "No supporting postings were retrieved for this line."
    conc = concentration(ev)
    top = ev[0]
    if conc >= 0.6:
        head = f"Driven by a single posting, {top.doc_id}, {top.description}"
    else:
        head = f"Spread across {len(ev)} postings, the largest being {top.doc_id}, {top.description}"
    if dec is None:
        return f"{head}. {line.direction.capitalize()} budget."
    # Share, not the amount. The amount is in the row above and repeating it wastes
    # the only two sentences anyone is going to read.
    share = abs(getattr(dec, dec.driver)) / abs(dec.total) if dec.total else 0.0
    return f"{head}. Mostly {dec.driver}, around {share:.0%} of the movement."


def claude_draft(line: Line, dec: Decomposition | None, ev: list[Entry]) -> str | None:
    """Ask Claude for the sentence. Returns None if no key, or on any failure.

    Failing closed matters more than failing clever. If this returns None the
    caller falls back to rules_draft and the pack still ships on time.
    """
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key or not ev:
        return None
    try:
        from anthropic import Anthropic
    except ImportError:
        return None

    payload = {
        "cost_centre": line.cost_centre,
        "account": line.account,
        "direction": line.direction,
        "decomposition": None if dec is None else {
            "rate": round(dec.rate, 2), "volume": round(dec.volume, 2),
            "joint": round(dec.joint, 2), "largest_term": dec.driver},
        "evidence": [
            {"doc_id": e.doc_id, "amount": round(e.amount, 2), "posted_on": e.posted_on,
             "description": e.description, "source": e.source} for e in ev],
        "evidence_concentration": round(concentration(ev), 2),
    }
    try:
        msg = Anthropic(api_key=key).messages.create(
            model=MODEL, max_tokens=220, system=SYSTEM,
            messages=[{"role": "user", "content": json.dumps(payload, indent=2)}],
        )
        return "".join(b.text for b in msg.content if b.type == "text").strip() or None
    except Exception:
        return None


def draft(line: Line, dec: Decomposition | None, ev: list[Entry]) -> tuple[str, list[str], bool, str]:
    """Returns (text, cites, needs_evidence, drafted_by)."""
    if not ev:
        return ("", [], True, "rules")
    cites = [e.doc_id for e in ev]
    text = claude_draft(line, dec, ev)
    if text:
        return (text, cites, False, "claude")
    return (rules_draft(line, dec, ev), cites, False, "rules")
