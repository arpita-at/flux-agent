"""Request and response shapes for the API."""
from __future__ import annotations

from pydantic import BaseModel, Field


class Rule(BaseModel):
    floor: float = Field(25_000.0, description="Absolute variance worth explaining")
    pct: float = Field(0.10, description="Share of budget worth explaining, 0.10 = 10%")
    ceiling: float = Field(500_000.0, description="Always explain above this, whatever the percentage")


class Commentary(BaseModel):
    cost_centre: str
    account: str
    actual: float
    budget: float
    variance: float
    pct: float | None
    direction: str
    driver: str | None = None
    text: str
    cites: list[str]
    needs_evidence: bool = False
    drafted_by: str  # "rules" | "claude"


class Pack(BaseModel):
    summary: dict
    commentary: list[Commentary]
    skipped: int
