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


def test_materiality_cannot_be_set_to_flag_everything():
    """floor=0, pct=0 would flag every line and bill a model call for each."""
    files = {n: (f"{n}.csv", b"cost_centre,account,amount\nCC-1,6200,10\n", "text/csv")
             for n in ("actuals", "budget", "prior")}
    files["ledger"] = ("ledger.csv",
                       b"doc_id,cost_centre,account,amount,posted_on,description,source\n", "text/csv")
    assert client.post("/api/pack?floor=0&pct=0", files=files).status_code == 422
    assert client.post("/api/pack?floor=-1&pct=0.1", files=files).status_code == 422
    assert client.post("/api/pack?floor=100&pct=0.1&ceiling=50", files=files).status_code == 422


def test_oversized_upload_is_refused_not_streamed():
    import app.main as m
    big = b"cost_centre,account,amount\n" + b"CC-1,6200,1\n" * 200_000
    files = {n: (f"{n}.csv", big if n == "actuals" else b"cost_centre,account,amount\n", "text/csv")
             for n in ("actuals", "budget", "prior")}
    files["ledger"] = ("ledger.csv",
                       b"doc_id,cost_centre,account,amount,posted_on,description,source\n", "text/csv")
    assert len(big) > m.MAX_BYTES
    assert client.post("/api/pack", files=files).status_code == 413


def test_draft_honours_the_model_call_cap():
    from app.evidence import Entry
    from app.explain import draft
    from app.variance import Line
    ev = [Entry("JE-1", "CC-1", "6200", 100.0, "2026-10-01", "x", "journal")]
    _, _, _, by = draft(Line("CC-1", "6200", 200, 100, 100), None, ev, allow_model=False)
    assert by == "rules"


def test_token_auth_rejects_a_wrong_token_and_accepts_the_right_one(monkeypatch):
    import app.main as m
    monkeypatch.setattr(m, "TOKEN", "s3cret")
    assert client.post("/api/demo").status_code == 401
    assert client.post("/api/demo", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.post("/api/demo", headers={"Authorization": "Bearer s3cret"}).status_code == 200
