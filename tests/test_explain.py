"""The control: no evidence means no sentence."""
from app.evidence import Entry, concentration, for_line
from app.explain import draft, rules_draft
from app.variance import Line, decompose

LINE = Line("CC-4100", "6200", 284_200, 216_000, 221_400)
EV = [
    Entry("JE-88120", "CC-4100", "6200", 61_400, "2026-10-28", "Contractor rate uplift", "journal"),
    Entry("JE-88121", "CC-4100", "6200", 4_300, "2026-10-29", "Two more contractors", "journal"),
]


def test_a_line_with_no_evidence_is_never_explained():
    text, cites, gap, by = draft(LINE, None, [])
    assert gap is True
    assert text == ""
    assert cites == []


def test_every_draft_cites_only_what_it_was_shown():
    text, cites, gap, by = draft(LINE, None, EV)
    assert gap is False
    assert cites == ["JE-88120", "JE-88121"]
    assert text


def test_concentration_separates_one_invoice_from_a_drift():
    assert concentration(EV) > 0.9                      # one posting did it
    even = [Entry(f"JE-{i}", "CC-1", "6200", 100, "2026-10-01", "x", "journal") for i in range(5)]
    assert concentration(even) == 0.2                   # it crept
    assert concentration([]) == 0.0


def test_rules_draft_never_restates_the_variance_number():
    dec = decompose(1200.0, 180.0, 1450.0, 196.0)
    text = rules_draft(LINE, dec, EV)
    assert "68,200" not in text          # the variance itself
    assert "rate" in text or "volume" in text or "joint" in text


def test_for_line_only_returns_that_cost_centre_and_account():
    mixed = EV + [Entry("JE-9", "CC-9999", "6200", 999_999, "2026-10-01", "other cc", "journal")]
    got = for_line(mixed, "CC-4100", "6200")
    assert [e.doc_id for e in got] == ["JE-88120", "JE-88121"]
