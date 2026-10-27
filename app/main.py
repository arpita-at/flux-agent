"""FastAPI app. Upload three CSVs and a ledger, get the commentary pack back.

Nothing here posts anything anywhere. The output is a draft pack for a person to
review. The human gate in the diagram is a person reading this output, not code.
"""
from __future__ import annotations

import csv
import io
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse

from .evidence import Entry
from .pipeline import load_lines, run
from .variance import Line, Materiality

SAMPLES = Path(__file__).resolve().parent.parent / "samples"
app = FastAPI(title="flux-agent", version="0.1.0",
              description="Month-end flux commentary. Rules in front of the model.")


def _rows(raw: bytes) -> list[dict]:
    return list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (Path(__file__).resolve().parent / "index.html").read_text(encoding="utf-8")


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


@app.post("/api/demo")
def demo() -> JSONResponse:
    """Run the synthetic sample end to end."""
    from .evidence import load_ledger
    lines = load_lines(SAMPLES / "actuals.csv", SAMPLES / "budget.csv", SAMPLES / "prior.csv")
    ledger = load_ledger(SAMPLES / "ledger.csv")
    drivers = {("CC-4100", "6200"): (1200.0, 180.0, 1450.0, 196.0)}
    return JSONResponse(run(lines, ledger, Materiality(), drivers))


@app.post("/api/pack")
async def pack(actuals: UploadFile = File(...), budget: UploadFile = File(...),
               prior: UploadFile = File(...), ledger: UploadFile = File(...),
               floor: float = 25_000.0, pct: float = 0.10,
               ceiling: float = 500_000.0) -> JSONResponse:
    def amounts(rows):
        return {(r["cost_centre"].strip(), r["account"].strip()): float(r["amount"]) for r in rows}
    a, b, p = amounts(_rows(await actuals.read())), amounts(_rows(await budget.read())), amounts(_rows(await prior.read()))
    keys = sorted(set(a) | set(b) | set(p))
    lines = [Line(cc, ac, a.get((cc, ac), 0.0), b.get((cc, ac), 0.0), p.get((cc, ac), 0.0))
             for cc, ac in keys]
    entries = [Entry(doc_id=r["doc_id"].strip(), cost_centre=r["cost_centre"].strip(),
                     account=r["account"].strip(), amount=float(r["amount"]),
                     posted_on=r["posted_on"].strip(), description=r["description"].strip(),
                     source=r.get("source", "journal").strip())
               for r in _rows(await ledger.read())]
    return JSONResponse(run(lines, entries, Materiality(floor, pct, ceiling)))
