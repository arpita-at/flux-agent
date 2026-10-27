from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_healthz():
    assert client.get("/healthz").json() == {"ok": True}


def test_demo_runs_the_sample_end_to_end():
    d = client.post("/api/demo").json()
    s = d["summary"]
    assert s["lines"] == 8
    assert s["flagged"] >= 3
    assert d["skipped"] == s["lines"] - s["flagged"]
    for c in d["commentary"]:
        # Every drafted line cites evidence; every uncited line is marked as a gap.
        assert bool(c["cites"]) != c["needs_evidence"]


def test_demo_flags_the_licence_renewal_first():
    d = client.post("/api/demo").json()
    assert d["commentary"][0]["cost_centre"] == "CC-4300"
