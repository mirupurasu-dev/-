"""期待値計算."""
from __future__ import annotations


def expected_value(prob: float, odds: float) -> float:
    """EV = odds * p - 1.  0 で等倍、+0.1 で+10%の期待."""
    return odds * prob - 1.0
