import numpy as np
import pandas as pd

from keiba_ai.backtest.signals import (
    SignalStats,
    _ndcg_at_k,
    _spearman_per_race,
    _win_logloss,
    compute_signal_stats,
    ic_weighted_score,
)


def test_spearman_perfect_positive():
    # x と ranks_desc が完全に一致 → IC=+1
    x = np.array([0.1, 0.5, 0.9])
    ranks_desc = np.array([1.0, 2.0, 3.0])
    ic = _spearman_per_race(x, ranks_desc)
    assert ic == 1.0


def test_spearman_perfect_negative():
    x = np.array([0.1, 0.5, 0.9])
    ranks_desc = np.array([3.0, 2.0, 1.0])
    ic = _spearman_per_race(x, ranks_desc)
    assert ic == -1.0


def test_ndcg_at_k_best_case():
    # scores と finish_pos が一致: 上位 k の gain 並びが最適
    scores = np.array([3.0, 2.0, 1.0, 0.5])
    finish_pos = np.array([1, 2, 3, 4])
    assert abs(_ndcg_at_k(scores, finish_pos, k=3) - 1.0) < 1e-9


def test_win_logloss_correct_top_has_lower_loss():
    scores_correct = np.array([5.0, 0.0, 0.0])
    scores_wrong = np.array([0.0, 5.0, 0.0])
    finish = np.array([1, 2, 3])
    ll_c = _win_logloss(scores_correct, finish)
    ll_w = _win_logloss(scores_wrong, finish)
    assert ll_c < ll_w


def test_compute_signal_stats_basic():
    """2レース分のダミー. ability_index が強く相関、noise_col はランダム."""
    rng = np.random.default_rng(42)
    rows = []
    for race_id in ["R1", "R2", "R3"]:
        n = 6
        ability = rng.normal(0, 1, n)
        finish = n - np.argsort(np.argsort(ability))  # 強い馬ほど上位 (低着順)
        noise = rng.normal(0, 1, n)
        for i in range(n):
            rows.append({
                "race_id": race_id,
                "horse_id": f"{race_id}_H{i}",
                "horse_no": i + 1,
                "ability_index": float(ability[i]),
                "noise_col": float(noise[i]),
                "label_finish": int(finish[i]),
            })
    df = pd.DataFrame(rows)
    stats = compute_signal_stats(df, signal_cols=["ability_index", "noise_col"])
    by_name = {s.name: s for s in stats}
    assert by_name["ability_index"].mean_ic > 0.5
    assert abs(by_name["noise_col"].mean_ic) < 0.5


def test_ic_weighted_score_correlates_with_ability():
    # ability_index だけ有意 → 重み付け合算は ability とほぼ一致
    rng = np.random.default_rng(0)
    rows = []
    for rid in range(10):
        n = 8
        ability = rng.normal(0, 1, n)
        for i in range(n):
            rows.append({
                "race_id": f"R{rid}",
                "horse_id": f"R{rid}_H{i}",
                "horse_no": i + 1,
                "ability_index": float(ability[i]),
                "noise_col": float(rng.normal(0, 1)),
                "label_finish": int(n - np.argsort(np.argsort(ability))[i]),
            })
    df = pd.DataFrame(rows).reset_index(drop=True)
    stats = compute_signal_stats(df, signal_cols=["ability_index", "noise_col"])
    scores = ic_weighted_score(df, stats)
    # ability と scores は同方向
    corr = np.corrcoef(scores, df["ability_index"].to_numpy())[0, 1]
    assert corr > 0.5
