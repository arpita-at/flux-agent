"""The arithmetic. If any of this breaks, every number in the pack is wrong."""
import pytest

from app.variance import Line, Materiality, decompose, flagged, summary


@pytest.mark.parametrize("p0,q0,p1,q1", [
    (1200.0, 180.0, 1450.0, 196.0),
    (10.0, 1.0, 10.0, 1.0),          # no movement
    (50.0, 100.0, 40.0, 130.0),      # rate down, volume up
    (0.0, 0.0, 12.5, 4.0),           # from nothing
    (99.99, 3.0, 12.25, 71.0),       # awkward numbers
])
def test_decomposition_sums_to_the_variance(p0, q0, p1, q1):
    dec = decompose(p0, q0, p1, q1)
    assert dec.total == pytest.approx(p1 * q1 - p0 * q0)


def test_driver_is_the_largest_absolute_term():
    dec = decompose(100.0, 10.0, 100.0, 40.0)   # pure volume
    assert dec.driver == "volume"
    dec = decompose(100.0, 10.0, 400.0, 10.0)   # pure rate
    assert dec.driver == "rate"


def test_materiality_needs_both_tests_not_either():
    rule = Materiality(floor=25_000, pct=0.10, ceiling=500_000)
    # Big percentage, trivial money. Must not reach the pack.
    assert rule.flags(variance=2_000, budget=500) is False
    # Big money, trivial percentage against a huge budget. Also not worth a sentence.
    assert rule.flags(variance=30_000, budget=10_000_000) is False
    # Both tests pass.
    assert rule.flags(variance=68_200, budget=216_000) is True


def test_ceiling_overrides_the_percentage_test():
    rule = Materiality(floor=25_000, pct=0.10, ceiling=500_000)
    assert rule.flags(variance=600_000, budget=100_000_000) is True


def test_zero_budget_falls_back_to_the_absolute_floor():
    rule = Materiality(floor=25_000, pct=0.10)
    assert rule.flags(variance=30_000, budget=0) is True
    assert rule.flags(variance=1_000, budget=0) is False


def test_flagged_is_ordered_by_size_not_by_input_order():
    lines = [
        Line("CC-1", "6200", 100_000, 10_000, 10_000),   # +90k
        Line("CC-2", "6200", 400_000, 10_000, 10_000),   # +390k
        Line("CC-3", "6200", 10_050, 10_000, 10_000),    # immaterial
    ]
    got = flagged(lines)
    assert [l.cost_centre for l in got] == ["CC-2", "CC-1"]


def test_coverage_reports_how_much_the_pack_actually_explains():
    lines = [
        Line("CC-1", "6200", 200_000, 100_000, 100_000),  # +100k, flagged
        Line("CC-2", "6200", 10_100, 10_000, 10_000),     # +100, skipped
    ]
    s = summary(lines, flagged(lines))
    assert s["flagged"] == 1
    assert s["total_variance"] == pytest.approx(100_100)
    assert s["coverage"] == pytest.approx(100_000 / 100_100, rel=1e-4)


def test_direction_and_movement_answer_different_questions():
    l = Line("CC-1", "6200", actual=120.0, budget=100.0, prior=130.0)
    assert l.direction == "over"      # against budget
    assert l.movement == -10.0        # against last month
