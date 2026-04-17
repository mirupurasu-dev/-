"""シグナル優位性分析: 各特徴量の予測力を測り、IC-重みで合成スコアを作る.

主要概念:
- Information Coefficient (IC)
    レース内で「シグナルの順位」と「実際の着順(降順)」の Spearman 相関
    +1に近いほど強い予測シグナル、0は無意味、-1は逆張り
- ICIR = mean(IC) / std(IC)
    ICの一貫性（シャープレシオ的な指標）
- 単独NDCG@k
    シグナル1個だけで並べた場合の上位一致度
- 単独 Win-LogLoss
    シグナルをsoftmaxしてP(1着)とし、実際の1着馬へのlog損失
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

from ..data.base import DataSource
from ..features.pipeline import FEATURE_COLS, build_features


@dataclass
class SignalStats:
    name: str
    n_races: int           # 有効レース数
    mean_ic: float         # 平均IC
    std_ic: float          # ICのばらつき
    icir: float            # ICIR = mean/std
    t_stat: float          # 検定統計量 (mean / (std/sqrt(n)))
    p_value: float         # 両側p値 (t分布)
    ndcg3: float           # 単独シグナルでのNDCG@3
    win_logloss: float     # softmax後のWin Log-Loss
    weight: float = 0.0    # IC-比重正規化後の推奨重み

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "n_races": self.n_races,
            "mean_ic": self.mean_ic,
            "std_ic": self.std_ic,
            "icir": self.icir,
            "t_stat": self.t_stat,
            "p_value": self.p_value,
            "ndcg3": self.ndcg3,
            "win_logloss": self.win_logloss,
            "weight": self.weight,
        }


def _spearman_per_race(x: np.ndarray, ranks_desc: np.ndarray) -> float:
    """x と ranks_desc(=n_runners+1-finish_pos) の Spearman 相関."""
    if len(x) < 3 or np.std(x) == 0 or np.std(ranks_desc) == 0:
        return np.nan
    # NaN 除外
    mask = np.isfinite(x) & np.isfinite(ranks_desc)
    if mask.sum() < 3:
        return np.nan
    xr = stats.rankdata(x[mask])
    yr = stats.rankdata(ranks_desc[mask])
    return float(np.corrcoef(xr, yr)[0, 1])


def _ndcg_at_k(scores: np.ndarray, finish_pos: np.ndarray, k: int = 3) -> float:
    """NDCG@k. gain = max(0, n - finish_pos + 1)."""
    if len(scores) == 0:
        return np.nan
    n = len(scores)
    gain = np.maximum(0.0, n - finish_pos + 1).astype(float)
    # 上位 k を取る
    order = np.argsort(-scores)[:k]
    dcg = 0.0
    for i, idx in enumerate(order):
        dcg += gain[idx] / math.log2(i + 2)
    # 理想値
    ideal_order = np.argsort(-gain)[:k]
    idcg = 0.0
    for i, idx in enumerate(ideal_order):
        idcg += gain[idx] / math.log2(i + 2)
    return dcg / idcg if idcg > 0 else np.nan


def _win_logloss(scores: np.ndarray, finish_pos: np.ndarray) -> float:
    """softmax(scores) を P(1着) とし、実1着への log-loss."""
    if len(scores) == 0 or not np.isfinite(scores).any():
        return np.nan
    s = scores - np.nanmax(scores)
    e = np.exp(s)
    p = e / e.sum()
    winner_idx = int(np.argmin(finish_pos))
    p_winner = max(p[winner_idx], 1e-9)
    return -math.log(p_winner)


def compute_signal_stats(
    feats: pd.DataFrame,
    signal_cols: list[str] | None = None,
) -> list[SignalStats]:
    """各シグナルの IC / ICIR / t統計 / NDCG@3 / Win-LogLoss を算出.

    Args:
        feats: build_features() の出力（label_finish を含む学習済データ）
        signal_cols: 評価対象の列名。None なら FEATURE_COLS を使う
    """
    cols = signal_cols or FEATURE_COLS
    feats = feats.dropna(subset=["label_finish"]).copy()
    if feats.empty:
        return []

    # race ごとに降順ランクラベル（高いほど上位着）
    races = list(feats.groupby("race_id", sort=False))
    n_races_total = len(races)

    # 各 signal ごとに IC / NDCG / logloss を蓄積
    per_signal_ic: dict[str, list[float]] = {c: [] for c in cols}
    per_signal_ndcg: dict[str, list[float]] = {c: [] for c in cols}
    per_signal_logloss: dict[str, list[float]] = {c: [] for c in cols}

    for _rid, g in races:
        if len(g) < 3:
            continue
        fp = g["label_finish"].to_numpy(dtype=float)
        n = len(g)
        ranks_desc = (n + 1) - fp  # 1着 → n, 最下位 → 1
        for c in cols:
            if c not in g.columns:
                continue
            x = g[c].to_numpy(dtype=float)
            ic = _spearman_per_race(x, ranks_desc)
            if np.isfinite(ic):
                per_signal_ic[c].append(ic)
            ndcg = _ndcg_at_k(x, fp, k=3)
            if np.isfinite(ndcg):
                per_signal_ndcg[c].append(ndcg)
            ll = _win_logloss(x, fp)
            if np.isfinite(ll):
                per_signal_logloss[c].append(ll)

    stats_list: list[SignalStats] = []
    for c in cols:
        ics = np.array(per_signal_ic[c])
        ndcgs = np.array(per_signal_ndcg[c])
        lls = np.array(per_signal_logloss[c])
        if len(ics) == 0:
            continue
        mean_ic = float(np.mean(ics))
        std_ic = float(np.std(ics, ddof=1)) if len(ics) > 1 else 0.0
        icir = mean_ic / std_ic if std_ic > 1e-9 else 0.0
        # 2-sided t-test against 0
        t_stat = mean_ic / (std_ic / math.sqrt(len(ics))) if std_ic > 1e-9 else 0.0
        # p値: t分布 df=n-1
        p_val = float(2 * (1 - stats.t.cdf(abs(t_stat), df=max(len(ics) - 1, 1)))) if std_ic > 1e-9 else 1.0
        stats_list.append(SignalStats(
            name=c,
            n_races=len(ics),
            mean_ic=mean_ic,
            std_ic=std_ic,
            icir=icir,
            t_stat=t_stat,
            p_value=p_val,
            ndcg3=float(np.mean(ndcgs)) if len(ndcgs) else np.nan,
            win_logloss=float(np.mean(lls)) if len(lls) else np.nan,
        ))

    # IC の絶対値で重み付け（符号は反映）。正規化して合計1
    abs_weights = np.array([max(abs(s.mean_ic), 0) for s in stats_list])
    if abs_weights.sum() > 0:
        normalized = abs_weights / abs_weights.sum()
        for s, w, raw in zip(stats_list, normalized, [sgn.mean_ic for sgn in stats_list]):
            s.weight = float(w * (1.0 if raw >= 0 else -1.0))

    # 降順にソート（|IC| 大きい順）
    stats_list.sort(key=lambda s: abs(s.mean_ic), reverse=True)
    return stats_list


def ic_weighted_score(feats: pd.DataFrame, stats_list: list[SignalStats]) -> np.ndarray:
    """IC-重みベクトルを使い、標準化された特徴量の線形結合でスコアを作る.

    各レース内で各特徴をz-score化し、重み×符号で合算。
    LightGBM と比較するベースラインとして機能する。
    """
    scores = np.zeros(len(feats))
    # レース内zscoreを取る
    for s in stats_list:
        if s.name not in feats.columns or abs(s.weight) < 1e-6:
            continue
        col = feats[s.name].to_numpy(dtype=float)
        z = np.zeros_like(col)
        for _rid, g in feats.groupby("race_id", sort=False):
            idx = g.index.to_numpy()
            x = col[idx]
            m = np.nanmean(x)
            sd = np.nanstd(x)
            if sd > 1e-9:
                z[idx] = (x - m) / sd
        scores += s.weight * z
    return scores


def analyze_signals_from_source(source: DataSource) -> list[SignalStats]:
    """DataSource から特徴量を作って IC分析を実行する便利関数."""
    races = source.load_races()
    runners = source.load_runners()
    results = source.load_results()
    feats = build_features(races, runners, results)
    return compute_signal_stats(feats)
