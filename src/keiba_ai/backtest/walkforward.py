"""Walk-forward バックテスト: 時系列分割で学習→買い目→払戻.

各レースで:
- 学習カットオフより前のデータで再学習
- 特徴量生成 → 予測 → 買い目推奨（当日オッズ）
- 実際の結果を突き合わせて PL を集計
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable

import numpy as np
import pandas as pd

from ..betting.recommender import recommend
from ..config import AppConfig
from ..data.base import DataSource
from ..features.pipeline import build_features
from ..models.pace_classifier import PACE_LABELS, PaceClassifier
from ..models.ranker import ScenarioRanker
from ..models.scenario_mix import mix_scenarios
from ..service import _scenario_from_first3f


@dataclass
class BacktestFold:
    train_end: datetime
    test_start: datetime
    test_end: datetime
    n_train_races: int
    n_test_races: int


@dataclass
class BacktestResult:
    total_stake: int
    total_payout: int
    roi: float                  # 回収率 = payout / stake (1.0で収支均衡)
    hit_rate: float             # 的中率 = 的中レース数 / 参加レース数
    hit_pick_rate: float        # 買い目単位の的中率
    n_races: int
    n_picks: int
    by_ticket: dict[str, dict]  # 券種別統計
    per_race_pl: list[dict] = field(default_factory=list)  # レース別 P&L


def _first1st_horse_no(results: pd.DataFrame, race_id: str) -> int | None:
    r = results[results["race_id"] == race_id]
    if r.empty:
        return None
    # finish_pos 最小の馬を取得 → horse_id → horse_no は runners から引く
    row = r.loc[r["finish_pos"].idxmin()]
    return None  # 未使用: 代わりに top3 を使う


def _finish_order(results: pd.DataFrame, runners: pd.DataFrame, race_id: str) -> list[int]:
    """horse_no の着順リストを返す. [1着の馬番, 2着の馬番, ...]"""
    r = results[results["race_id"] == race_id].copy()
    rn = runners[runners["race_id"] == race_id][["horse_id", "horse_no"]]
    r = r.merge(rn, on="horse_id", how="left")
    r = r.sort_values("finish_pos")
    return r["horse_no"].dropna().astype(int).tolist()


def _payout_for_pick(ticket: str, selection: str, order: list[int], odds: float) -> int:
    """当たれば (odds * 100) を返す（100円ベット前提で後でstakeにスケール）. 外れは0."""
    if not order:
        return 0
    s = selection
    if ticket == "win":
        return int(odds * 100) if int(s) == order[0] else 0
    if ticket == "place":
        top3 = set(order[:3])
        return int(odds * 100) if int(s) in top3 else 0
    if ticket == "quinella":
        a, b = [int(x) for x in s.split("-")]
        return int(odds * 100) if {a, b} == set(order[:2]) else 0
    if ticket == "exacta":
        a, b = [int(x) for x in s.split("->")]
        return int(odds * 100) if (a, b) == (order[0], order[1]) else 0
    if ticket == "trio":
        a, b, c = [int(x) for x in s.split("-")]
        return int(odds * 100) if {a, b, c} == set(order[:3]) else 0
    if ticket == "trifecta":
        a, b, c = [int(x) for x in s.split("->")]
        return int(odds * 100) if (a, b, c) == tuple(order[:3]) else 0
    return 0


def _build_odds_dict(odds_df: pd.DataFrame, race_id: str, runners: pd.DataFrame) -> dict:
    """当日確定オッズから買い目評価用 dict を構築（win/place のみ。他券種は省略）."""
    row_odds = odds_df[odds_df["race_id"] == race_id]
    if row_odds.empty:
        return {}
    win = {int(r["horse_no"]): float(r["win"]) for _, r in row_odds.iterrows()}
    place = {int(r["horse_no"]): (float(r["place_low"]), float(r["place_high"])) for _, r in row_odds.iterrows()}
    return {"win": win, "place": place, "quinella": {}, "exacta": {}, "trio": {}, "trifecta": {}}


def walk_forward_backtest(
    source: DataSource,
    cfg: AppConfig,
    *,
    min_train_races: int = 400,
    n_folds: int = 3,
    allowed_tickets: Iterable[str] | None = None,
    budget: int = 10000,
) -> tuple[list[BacktestFold], BacktestResult]:
    """時系列で n_folds に分割し、各fold で train→test のシミュレーションを実行."""
    races = source.load_races().copy()
    runners = source.load_runners()
    results = source.load_results()
    odds_df = source.load_odds()
    if races.empty:
        raise RuntimeError("レースデータがありません")

    races["date"] = pd.to_datetime(races["date"])
    races = races.sort_values("date").reset_index(drop=True)
    n_total = len(races)
    if n_total < min_train_races + n_folds:
        raise RuntimeError(f"データ不足: {n_total} レース < {min_train_races + n_folds}")

    # chronological split
    test_size = (n_total - min_train_races) // n_folds
    folds_info: list[BacktestFold] = []
    splits: list[tuple[int, int]] = []
    for k in range(n_folds):
        train_end_idx = min_train_races + k * test_size
        test_start_idx = train_end_idx
        test_end_idx = min(train_end_idx + test_size, n_total)
        if test_end_idx - test_start_idx < 5:
            break
        splits.append((train_end_idx, test_end_idx))
        folds_info.append(BacktestFold(
            train_end=races.loc[train_end_idx - 1, "date"].to_pydatetime(),
            test_start=races.loc[test_start_idx, "date"].to_pydatetime(),
            test_end=races.loc[test_end_idx - 1, "date"].to_pydatetime(),
            n_train_races=train_end_idx,
            n_test_races=test_end_idx - test_start_idx,
        ))

    from ..config import BettingConfig
    betting_cfg = BettingConfig(
        ev_threshold=cfg.betting.ev_threshold,
        kelly_fraction=cfg.betting.kelly_fraction,
        stake_cap=cfg.betting.stake_cap,
        min_stake=cfg.betting.min_stake,
        max_picks=cfg.betting.max_picks,
        allowed_tickets=list(allowed_tickets or ["win", "place"]),
    )

    total_stake = 0
    total_payout = 0
    n_picks = 0
    n_picks_hit = 0
    n_races_participated = 0
    n_races_hit = 0
    by_ticket: dict[str, dict] = {}
    per_race_pl: list[dict] = []

    for (train_end_idx, test_end_idx) in splits:
        train_races = races.iloc[:train_end_idx]
        test_races = races.iloc[train_end_idx:test_end_idx]
        train_race_ids = set(train_races["race_id"])
        test_race_ids = list(test_races["race_id"])

        # 学習: train データのみ使う
        train_runners = runners[runners["race_id"].isin(train_race_ids)]
        train_results = results[results["race_id"].isin(train_race_ids)]
        train_feats = build_features(train_races, train_runners, train_results)
        train_feats = train_feats.dropna(subset=["label_finish"]).reset_index(drop=True)

        # ペース教師（train-only）
        race_pace = (
            train_results.groupby("race_id")["first3f_sec"].mean().rename("race_first3f_mean").reset_index()
        )
        race_pace = race_pace.merge(train_races[["race_id", "distance_m"]], on="race_id", how="left")
        race_pace["pace_label"] = race_pace.apply(
            lambda r: _scenario_from_first3f(r["race_first3f_mean"], r["distance_m"]), axis=1
        )

        # ペース分類器（簡易: defaultパラメータ）
        from ..features.pipeline import pace_forecast_features
        pace_df_tr = pace_forecast_features(train_feats)
        pace_df_tr = pace_df_tr.merge(race_pace[["race_id", "pace_label"]], on="race_id", how="inner")
        if pace_df_tr.empty:
            continue
        pace_model = PaceClassifier().fit(pace_df_tr, pace_df_tr["pace_label"])

        # Ranker
        feats_tr_lbl = train_feats.merge(race_pace[["race_id", "pace_label"]], on="race_id", how="left")
        ranker = ScenarioRanker()
        for scenario in PACE_LABELS:
            sub = feats_tr_lbl[feats_tr_lbl["pace_label"] == scenario]
            if len(sub) > 100:
                ranker.fit_scenario(sub, scenario)
            else:
                ranker.fit_scenario(feats_tr_lbl, scenario)

        # テストレース: 全履歴（train+過去のtest）を使って as_of で特徴を作る
        #   ただし build_features は既に race_date 未来を参照しない設計
        all_up_to_test = races.iloc[:test_end_idx]
        all_rids = set(all_up_to_test["race_id"])
        sub_runners = runners[runners["race_id"].isin(all_rids)]
        sub_results = results[results["race_id"].isin(all_rids)]

        for rid in test_race_ids:
            try:
                feats = build_features(all_up_to_test, sub_runners, sub_results, target_race_ids=[rid]).reset_index(drop=True)
                if feats.empty:
                    continue
                pace_probs = pace_model.predict_dict(pace_forecast_features(feats))[0]
                scores_by = {sc: ranker.predict_scores(feats, sc) for sc in PACE_LABELS}
                mixed = mix_scenarios(scores_by, pace_probs)
                rep_scores = np.zeros(len(feats))
                for sc, p in pace_probs.items():
                    rep_scores += p * scores_by[sc]

                horse_nos = feats["horse_no"].astype(int).tolist()
                odds = _build_odds_dict(odds_df, rid, runners)
                if not odds:
                    continue

                rec = recommend(
                    race_id=rid,
                    horse_nos=horse_nos,
                    scores=rep_scores,
                    p1=mixed["p1"],
                    place_prob=mixed["place"],
                    odds=odds,
                    budget=budget,
                    cfg=betting_cfg,
                )
                if not rec.picks:
                    continue

                order = _finish_order(results, runners, rid)
                race_stake = 0
                race_payout = 0
                race_hit = False
                for p in rec.picks:
                    payout = _payout_for_pick(p.ticket.value, p.selection, order, p.odds) * (p.stake // 100)
                    race_stake += p.stake
                    race_payout += payout
                    n_picks += 1
                    hit = payout > 0
                    if hit:
                        n_picks_hit += 1
                        race_hit = True
                    bt = by_ticket.setdefault(p.ticket.value, {"stake": 0, "payout": 0, "picks": 0, "hits": 0})
                    bt["stake"] += p.stake
                    bt["payout"] += payout
                    bt["picks"] += 1
                    bt["hits"] += 1 if hit else 0

                total_stake += race_stake
                total_payout += race_payout
                n_races_participated += 1
                if race_hit:
                    n_races_hit += 1
                per_race_pl.append({
                    "race_id": rid,
                    "stake": race_stake,
                    "payout": race_payout,
                    "pl": race_payout - race_stake,
                    "hit": race_hit,
                })
            except Exception:
                continue

    # 集計
    for k, v in by_ticket.items():
        v["roi"] = v["payout"] / v["stake"] if v["stake"] > 0 else 0.0
        v["hit_rate"] = v["hits"] / v["picks"] if v["picks"] > 0 else 0.0

    result = BacktestResult(
        total_stake=int(total_stake),
        total_payout=int(total_payout),
        roi=(total_payout / total_stake) if total_stake > 0 else 0.0,
        hit_rate=(n_races_hit / n_races_participated) if n_races_participated > 0 else 0.0,
        hit_pick_rate=(n_picks_hit / n_picks) if n_picks > 0 else 0.0,
        n_races=n_races_participated,
        n_picks=n_picks,
        by_ticket=by_ticket,
        per_race_pl=per_race_pl,
    )
    return folds_info, result
