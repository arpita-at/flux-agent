"""FastAPI app. Upload three CSVs and a ledger, get the commentary pack back.

Nothing here posts anything anywhere. The output is a draft pack for a person to
review. The human gate in the diagram is a person reading this output, not code.
"""
from __future__ import annotations

import csv
import io
from pathlib import Path

import os

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse

from .evidence import Entry
from .pipeline import load_lines, run
from .variance import Line, Materiality

SAMPLES = Path(__file__).resolve().parent.parent / "samples"

# Limits. Every flagged line can cost one model call, so an unbounded upload is an
# unbounded bill. These are deliberately small; raise them for your own deployment.
MAX_BYTES = int(os.environ.get("FLUX_MAX_BYTES", 2 * 1024 * 1024))
MAX_ROWS = int(os.environ.get("FLUX_MAX_ROWS", 20_000))
TOKEN = os.environ.get("FLUX_API_TOKEN")  # set it and every endpoint requires it


def auth(authorization: str | None = Header(default=None)) -> None:
    """No token configured means local use and no auth. Set FLUX_API_TOKEN before
    exposing this to a network, or you are paying for other people's model calls."""
    if not TOKEN:
        return
    if authorization != f"Bearer {TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")


async def read_capped(f: UploadFile, name: str) -> bytes:
    raw = await f.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise HTTPException(413, f"{name} is larger than {MAX_BYTES} bytes")
    return raw
app = FastAPI(title="flux-agent", version="0.1.0",
              description="Month-end flux commentary. Rules in front of the model.")


def _rows(raw: bytes, name: str) -> list[dict]:
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    if len(rows) > MAX_ROWS:
        raise HTTPException(413, f"{name} has more than {MAX_ROWS} rows")
    return rows


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (Path(__file__).resolve().parent / "index.html").read_text(encoding="utf-8")


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


@app.post("/api/demo", dependencies=[Depends(auth)])
def demo() -> JSONResponse:
    """Run the synthetic sample end to end."""
    from .evidence import load_ledger
    lines = load_lines(SAMPLES / "actuals.csv", SAMPLES / "budget.csv", SAMPLES / "prior.csv")
    ledger = load_ledger(SAMPLES / "ledger.csv")
    drivers = {("CC-4100", "6200"): (1200.0, 180.0, 1450.0, 196.0)}
    return JSONResponse(run(lines, ledger, Materiality(), drivers))


@app.post("/api/pack", dependencies=[Depends(auth)])
async def pack(actuals: UploadFile = File(...), budget: UploadFile = File(...),
               prior: UploadFile = File(...), ledger: UploadFile = File(...),
               floor: float = 25_000.0, pct: float = 0.10,
               ceiling: float = 500_000.0) -> JSONResponse:
    # A caller passing floor=0, pct=0 would flag every line and bill a model call for
    # each one. The thresholds are a cost control as much as a reporting policy.
    if floor < 0 or ceiling < 0 or not (0.0 < pct <= 10.0) or ceiling < floor:
        raise HTTPException(422, "Invalid materiality: need floor >= 0, 0 < pct <= 10, ceiling >= floor")

    def amounts(rows):
        return {(r["cost_centre"].strip(), r["account"].strip()): float(r["amount"]) for r in rows}
    a = amounts(_rows(await read_capped(actuals, "actuals"), "actuals"))
    b = amounts(_rows(await read_capped(budget, "budget"), "budget"))
    p = amounts(_rows(await read_capped(prior, "prior"), "prior"))
    keys = sorted(set(a) | set(b) | set(p))
    lines = [Line(cc, ac, a.get((cc, ac), 0.0), b.get((cc, ac), 0.0), p.get((cc, ac), 0.0))
             for cc, ac in keys]
    entries = [Entry(doc_id=r["doc_id"].strip(), cost_centre=r["cost_centre"].strip(),
                     account=r["account"].strip(), amount=float(r["amount"]),
                     posted_on=r["posted_on"].strip(), description=r["description"].strip(),
                     source=r.get("source", "journal").strip())
               for r in _rows(await read_capped(ledger, "ledger"), "ledger")]
    return JSONResponse(run(lines, entries, Materiality(floor, pct, ceiling)))
