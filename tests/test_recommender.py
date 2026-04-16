from datetime import datetime

import numpy as np

from keiba_ai.config import BettingConfig
from keiba_ai.betting.recommender import recommend


def test_recommend_picks_positive_ev_win():
    # 3頭のレース。馬1が過小評価（p=0.6 なのにオッズ 3.0 → EV = 0.8）
    horse_nos = [1, 2, 3]
    scores = np.array([1.5, 0.5, -0.5])
    p1 = np.array([0.6, 0.3, 0.1])
    place_prob = np.array([0.9, 0.7, 0.4])
    odds = {
        "win": {1: 3.0, 2: 3.5, 3: 10.0},
        "place": {1: (1.3, 1.5), 2: (1.5, 1.8), 3: (3.0, 4.0)},
        "quinella": {"1-2": 5.0, "1-3": 8.0, "2-3": 12.0},
        "exacta": {},
        "trio": {},
        "trifecta": {},
    }
    cfg = BettingConfig(ev_threshold=0.1, kelly_fraction=0.25, stake_cap=0.05,
                         min_stake=100, max_picks=5,
                         allowed_tickets=["win", "place", "quinella"])
    rec = recommend(
        race_id="R1", horse_nos=horse_nos, scores=scores,
        p1=p1, place_prob=place_prob, odds=odds, budget=10000, cfg=cfg,
        now=datetime(2024, 1, 1),
    )
    # 少なくとも単勝1が推奨される
    sel = [p.selection for p in rec.picks if p.ticket.value == "win"]
    assert "1" in sel
    assert rec.total_stake > 0
    assert rec.total_stake <= 10000


def test_recommend_no_picks_when_no_value():
    horse_nos = [1, 2]
    scores = np.array([0.2, -0.2])
    p1 = np.array([0.5, 0.5])
    place = np.array([1.0, 1.0])
    # EV が閾値を超えない（p×odds ≤ 1.10）
    odds = {"win": {1: 2.0, 2: 2.0}, "place": {}, "quinella": {}, "exacta": {}, "trio": {}, "trifecta": {}}
    cfg = BettingConfig(ev_threshold=0.1, kelly_fraction=0.25, stake_cap=0.05,
                         min_stake=100, max_picks=5,
                         allowed_tickets=["win"])
    rec = recommend("R2", horse_nos, scores, p1, place, odds, budget=10000, cfg=cfg)
    assert len(rec.picks) == 0
    assert rec.total_stake == 0
