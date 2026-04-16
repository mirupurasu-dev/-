"""買い目推奨: EV 閾値 + 分数ケリー + 予算制約."""
from __future__ import annotations

from datetime import datetime
from itertools import combinations, permutations

import numpy as np

from ..config import BettingConfig
from ..data.schema import BetRecommendation, RaceRecommendation, TicketType
from ..models.plackett_luce import (
    exacta_prob,
    quinella_prob,
    trifecta_prob,
    trio_prob,
)
from .expected_value import expected_value
from .kelly import fractional_kelly_stake


def _num_to_index(horse_no: int, horse_nos: list[int]) -> int:
    return horse_nos.index(horse_no)


def recommend(
    race_id: str,
    horse_nos: list[int],
    scores: np.ndarray,
    p1: np.ndarray,
    place_prob: np.ndarray,
    odds: dict,
    budget: int,
    cfg: BettingConfig,
    *,
    now: datetime | None = None,
) -> RaceRecommendation:
    """各券種を列挙し、期待値閾値を超えるものから分数ケリーで推奨を組む.

    Args:
        horse_nos: 出走順に並んだ馬番リスト（len = N）
        scores: 各馬のランキングスコア（Plackett-Luce 用）
        p1: 合成後 P(1着), shape (N,)
        place_prob: 合成後 P(複勝), shape (N,)
        odds: {"win":{馬番: 倍率}, "place":{馬番:(下限,上限)}, "quinella":{"i-j":倍率}, "exacta":{"i->j"}, "trio":{"i-j-k"}, "trifecta":{"i->j->k"}}
        budget: 予算（円）
    """
    now = now or datetime.utcnow()
    allowed = set(cfg.allowed_tickets)
    candidates: list[BetRecommendation] = []

    idx = {no: i for i, no in enumerate(horse_nos)}

    # --- 単勝 ---
    if "win" in allowed:
        for no, price in odds.get("win", {}).items():
            if no not in idx or price <= 1.0:
                continue
            i = idx[no]
            p = float(p1[i])
            ev = expected_value(p, price)
            if ev > cfg.ev_threshold:
                candidates.append(BetRecommendation(
                    ticket=TicketType.WIN, selection=str(no),
                    odds=float(price), probability=p, expected_value=ev,
                    kelly_fraction=0.0, stake=0,
                ))

    # --- 複勝（下限で保守的に評価） ---
    if "place" in allowed:
        for no, bounds in odds.get("place", {}).items():
            if no not in idx:
                continue
            lo = bounds[0] if isinstance(bounds, (tuple, list)) else float(bounds)
            if lo <= 1.0:
                continue
            i = idx[no]
            p = float(place_prob[i])
            ev = expected_value(p, lo)
            if ev > cfg.ev_threshold:
                candidates.append(BetRecommendation(
                    ticket=TicketType.PLACE, selection=str(no),
                    odds=float(lo), probability=p, expected_value=ev,
                    kelly_fraction=0.0, stake=0,
                ))

    # --- 馬連 ---
    if "quinella" in allowed:
        for key, price in odds.get("quinella", {}).items():
            try:
                a, b = [int(x) for x in key.split("-")]
            except Exception:
                continue
            if a not in idx or b not in idx or price <= 1.0:
                continue
            p = quinella_prob(scores, idx[a], idx[b])
            ev = expected_value(p, price)
            if ev > cfg.ev_threshold:
                candidates.append(BetRecommendation(
                    ticket=TicketType.QUINELLA, selection=f"{a}-{b}",
                    odds=float(price), probability=p, expected_value=ev,
                    kelly_fraction=0.0, stake=0,
                ))

    # --- 馬単 ---
    if "exacta" in allowed:
        for key, price in odds.get("exacta", {}).items():
            try:
                a, b = [int(x) for x in key.split("->")]
            except Exception:
                continue
            if a not in idx or b not in idx or price <= 1.0:
                continue
            p = exacta_prob(scores, idx[a], idx[b])
            ev = expected_value(p, price)
            if ev > cfg.ev_threshold:
                candidates.append(BetRecommendation(
                    ticket=TicketType.EXACTA, selection=f"{a}->{b}",
                    odds=float(price), probability=p, expected_value=ev,
                    kelly_fraction=0.0, stake=0,
                ))

    # --- 3連複 ---
    if "trio" in allowed:
        for key, price in odds.get("trio", {}).items():
            try:
                a, b, c = sorted(int(x) for x in key.split("-"))
            except Exception:
                continue
            if any(x not in idx for x in (a, b, c)) or price <= 1.0:
                continue
            p = trio_prob(scores, idx[a], idx[b], idx[c])
            ev = expected_value(p, price)
            if ev > cfg.ev_threshold:
                candidates.append(BetRecommendation(
                    ticket=TicketType.TRIO, selection=f"{a}-{b}-{c}",
                    odds=float(price), probability=p, expected_value=ev,
                    kelly_fraction=0.0, stake=0,
                ))

    # --- 3連単 ---
    if "trifecta" in allowed:
        for key, price in odds.get("trifecta", {}).items():
            try:
                a, b, c = [int(x) for x in key.split("->")]
            except Exception:
                continue
            if any(x not in idx for x in (a, b, c)) or price <= 1.0:
                continue
            p = trifecta_prob(scores, idx[a], idx[b], idx[c])
            ev = expected_value(p, price)
            if ev > cfg.ev_threshold:
                candidates.append(BetRecommendation(
                    ticket=TicketType.TRIFECTA, selection=f"{a}->{b}->{c}",
                    odds=float(price), probability=p, expected_value=ev,
                    kelly_fraction=0.0, stake=0,
                ))

    # EV 降順で並べ、最大点数まで
    candidates.sort(key=lambda x: x.expected_value, reverse=True)
    candidates = candidates[: cfg.max_picks]

    # ケリー割付（予算内で按分）
    total_stake = 0
    picks_out: list[BetRecommendation] = []
    remaining = budget
    for c in candidates:
        stake = fractional_kelly_stake(
            prob=c.probability,
            odds=c.odds,
            bankroll=budget,
            fraction=cfg.kelly_fraction,
            cap=cfg.stake_cap,
            min_stake=cfg.min_stake,
        )
        stake = min(stake, remaining)
        stake = (stake // cfg.min_stake) * cfg.min_stake
        if stake < cfg.min_stake:
            continue
        from .kelly import kelly_fraction as _kf
        c.stake = int(stake)
        c.kelly_fraction = float(_kf(c.probability, c.odds))
        picks_out.append(c)
        total_stake += stake
        remaining -= stake
        if remaining < cfg.min_stake:
            break

    expected_profit = sum(p.stake * p.expected_value for p in picks_out)

    return RaceRecommendation(
        race_id=race_id,
        budget=int(budget),
        picks=picks_out,
        total_stake=int(total_stake),
        expected_profit=float(expected_profit),
        computed_at=now,
    )


def enumerate_all_tickets(horse_nos: list[int], tickets: list[str]) -> dict[str, list[str]]:
    """全券種の組み合わせを列挙（Mockオッズ生成用）."""
    out: dict[str, list[str]] = {}
    if "win" in tickets:
        out["win"] = [str(n) for n in horse_nos]
    if "place" in tickets:
        out["place"] = [str(n) for n in horse_nos]
    if "quinella" in tickets:
        out["quinella"] = [f"{a}-{b}" for a, b in combinations(horse_nos, 2)]
    if "exacta" in tickets:
        out["exacta"] = [f"{a}->{b}" for a, b in permutations(horse_nos, 2)]
    if "trio" in tickets:
        out["trio"] = [f"{a}-{b}-{c}" for a, b, c in combinations(horse_nos, 3)]
    if "trifecta" in tickets:
        out["trifecta"] = [f"{a}->{b}->{c}" for a, b, c in permutations(horse_nos, 3)]
    return out
