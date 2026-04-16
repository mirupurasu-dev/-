from keiba_ai.betting.expected_value import expected_value
from keiba_ai.betting.kelly import fractional_kelly_stake, kelly_fraction


def test_expected_value():
    assert expected_value(0.5, 3.0) == 0.5
    assert expected_value(0.4, 2.5) == 0.0
    assert expected_value(0.2, 5.0) == 0.0


def test_kelly_zero_when_no_edge():
    assert kelly_fraction(0.3, 3.0) == 0.0  # edge = 0.9 - 1 = -0.1
    assert kelly_fraction(0.4, 2.5) == 0.0  # edge = 0


def test_kelly_positive_edge():
    # p=0.4, odds=3.0 → edge=0.2, f* = 0.2/2.0 = 0.1
    assert abs(kelly_fraction(0.4, 3.0) - 0.1) < 1e-9


def test_fractional_stake_rounding():
    # bankroll=10000, f*=0.1 → fraction 0.25 → ratio=0.025 → 250円
    s = fractional_kelly_stake(0.4, 3.0, 10000, fraction=0.25, cap=0.05, min_stake=100)
    assert s == 200  # 250を100円単位に切り下げ


def test_stake_cap():
    # 巨大エッジでも cap 5% まで
    s = fractional_kelly_stake(0.9, 5.0, 10000, fraction=1.0, cap=0.05, min_stake=100)
    assert s == 500


def test_stake_zero_for_negative_ev():
    assert fractional_kelly_stake(0.1, 3.0, 10000) == 0
