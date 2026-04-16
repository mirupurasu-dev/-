"""分数ケリー基準による掛け金算出."""
from __future__ import annotations


def kelly_fraction(prob: float, odds: float) -> float:
    """フルケリー比率 f* = (b*p - 1) / (b - 1), where b = odds."""
    if odds <= 1.0 or prob <= 0.0:
        return 0.0
    edge = odds * prob - 1.0
    if edge <= 0:
        return 0.0
    return edge / (odds - 1.0)


def fractional_kelly_stake(
    prob: float,
    odds: float,
    bankroll: float,
    fraction: float = 0.25,
    cap: float = 0.05,
    min_stake: int = 100,
) -> int:
    """分数ケリー掛け金（円、100円刻み）を返す. 期待値がマイナスなら 0."""
    f_star = kelly_fraction(prob, odds)
    if f_star <= 0:
        return 0
    stake_ratio = min(f_star * fraction, cap)
    raw = bankroll * stake_ratio
    # 100円単位に丸め（切り下げ）
    stake = int(raw // min_stake) * min_stake
    return max(stake, 0)
