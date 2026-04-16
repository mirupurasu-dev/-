"""特徴量パイプライン: 過去レース履歴から学習/推論用のDataFrameを生成.

リーク対策:
- 各レース `r` の特徴量は、`r.date` より厳密に前の結果のみから算出する
- 今レースの着順や上がりタイムは使わない（当然）
"""
from __future__ import annotations

import numpy as np
import pandas as pd


STYLE_LABELS = ["nige", "senko", "sashi", "oikomi"]


def _style_from_corner(corner_pos: int, n_runners: int) -> str:
    """コーナー通過順 / 頭数 から脚質ラベルを推定."""
    rel = corner_pos / max(n_runners, 1)
    if rel <= 0.15:
        return "nige"
    if rel <= 0.40:
        return "senko"
    if rel <= 0.75:
        return "sashi"
    return "oikomi"


def _rolling_style_probs(corner_positions: list[int], n_runners_list: list[int]) -> dict[str, float]:
    """直近数走から脚質確率ベクトルを出す. EWMA風の重み."""
    if not corner_positions:
        return {s: 0.25 for s in STYLE_LABELS}
    weights = np.array([0.5 ** i for i in range(len(corner_positions))])
    weights /= weights.sum()
    counts = {s: 0.0 for s in STYLE_LABELS}
    for cp, nr, w in zip(corner_positions, n_runners_list, weights):
        counts[_style_from_corner(cp, nr)] += w
    total = sum(counts.values()) or 1.0
    return {s: counts[s] / total for s in STYLE_LABELS}


def _zscore(series: pd.Series) -> pd.Series:
    m = series.mean()
    s = series.std(ddof=0) or 1.0
    return (series - m) / s


def _devscore(series: pd.Series) -> pd.Series:
    """偏差値（平均50, 標準偏差10）."""
    return 50.0 + 10.0 * _zscore(series)


def build_features(
    races: pd.DataFrame,
    runners: pd.DataFrame,
    results: pd.DataFrame,
    *,
    history_window: int = 5,
    target_race_ids: list[str] | set[str] | None = None,
) -> pd.DataFrame:
    """学習・推論両用の特徴量テーブルを生成.

    Returns:
        DataFrame(row: race_id × horse_id)
        columns: race_id, horse_id, horse_no, draw, distance_m, surface, turn,
                 track_condition, n_runners, course, age, weight_kg,
                 p_nige, p_senko, p_sashi, p_oikomi,
                 ten_index, agari_index, ability_index,
                 dist_fit, surface_fit, track_cond_fit,
                 course_place_rate, days_since_last, field_size,
                 label_finish (欠損可, 推論時)
    """
    races = races.copy()
    races["date"] = pd.to_datetime(races["date"])
    results = results.copy()
    # 結果にレース日を結合
    rd = results.merge(races[["race_id", "date", "n_runners", "distance_m", "surface", "track_condition", "course"]], on="race_id", how="left")
    rd = rd.sort_values(["horse_id", "date"]).reset_index(drop=True)

    # 各 (horse_id, date) に対して「その日より前」の過去走を集計
    rd_by_horse: dict[str, pd.DataFrame] = {h: g.reset_index(drop=True) for h, g in rd.groupby("horse_id")}

    feat_rows: list[dict] = []
    runners_with_race = runners.merge(races, on="race_id", how="left", suffixes=("", "_race"))
    if target_race_ids is not None:
        target_set = set(target_race_ids)
        runners_with_race = runners_with_race[runners_with_race["race_id"].isin(target_set)]

    for _, r in runners_with_race.iterrows():
        race_id = r["race_id"]
        horse_id = r["horse_id"]
        race_date = r["date"]
        distance_m = r["distance_m"]
        surface = r["surface"]
        track_cond = r["track_condition"]
        course = r["course"]
        n_runners = r["n_runners"]

        hist = rd_by_horse.get(horse_id)
        if hist is not None:
            hist = hist[hist["date"] < race_date].tail(history_window)
        else:
            hist = pd.DataFrame()

        if hist.empty:
            style_probs = {s: 0.25 for s in STYLE_LABELS}
            ten_raw = np.nan
            agari_raw = np.nan
            ability_raw = np.nan
            dist_fit = 0.0
            surface_fit = 0.0
            track_cond_fit = 0.0
            course_place_rate = 0.0
            days_since_last = 999
        else:
            # 脚質確率（直近→過去への重み付き）
            corner_list = hist["corner1"].tolist()[::-1]  # 直近が先頭
            nrun_list = hist["n_runners"].tolist()[::-1]
            style_probs = _rolling_style_probs(corner_list, nrun_list)

            # テン指数: 前半3Fが低いほど速い → 符号反転して高い=速い
            # コース補正: 距離と馬場で z-score 化する代わりに、母集団（全体）から計算する
            ten_raw = -(hist["first3f_sec"].mean() if hist["first3f_sec"].notna().any() else np.nan)

            # 上がり指数: last3f_sec が低いほど速い → 符号反転
            agari_raw = -hist["last3f_sec"].mean()

            # 総合実力: 「本来なら勝てる相手に対する相対走破タイム」の代理として
            # 「着順 / 頭数」 を使う（低いほど強い）→ 符号反転
            ability_raw = -(hist["finish_pos"] / hist["n_runners"]).mean()

            # 距離適性: 同距離±200m レンジの複勝率
            same_dist = hist[(hist["distance_m"] >= distance_m - 200) & (hist["distance_m"] <= distance_m + 200)]
            dist_fit = (same_dist["finish_pos"] <= 3).mean() if len(same_dist) else 0.0

            # 馬場適性: 同surfaceの複勝率
            same_surf = hist[hist["surface"] == surface]
            surface_fit = (same_surf["finish_pos"] <= 3).mean() if len(same_surf) else 0.0

            # 馬場状態適性
            same_tc = hist[hist["track_condition"] == track_cond]
            track_cond_fit = (same_tc["finish_pos"] <= 3).mean() if len(same_tc) else 0.0

            # 同コース複勝率
            same_course = hist[hist["course"] == course]
            course_place_rate = (same_course["finish_pos"] <= 3).mean() if len(same_course) else 0.0

            # 休養明け日数
            last_date = hist["date"].max()
            days_since_last = int((race_date - last_date).days)

        feat_rows.append({
            "race_id": race_id,
            "horse_id": horse_id,
            "horse_no": int(r["horse_no"]),
            "draw": int(r["draw"]),
            "distance_m": int(distance_m),
            "surface": surface,
            "turn": r["turn"],
            "track_condition": track_cond,
            "n_runners": int(n_runners),
            "course": course,
            "age": int(r["age"]),
            "weight_kg": float(r["weight_kg"]),
            "p_nige": style_probs["nige"],
            "p_senko": style_probs["senko"],
            "p_sashi": style_probs["sashi"],
            "p_oikomi": style_probs["oikomi"],
            "ten_raw": ten_raw,
            "agari_raw": agari_raw,
            "ability_raw": ability_raw,
            "dist_fit": dist_fit,
            "surface_fit": surface_fit,
            "track_cond_fit": track_cond_fit,
            "course_place_rate": course_place_rate,
            "days_since_last": days_since_last,
            "race_date": race_date,
        })

    df = pd.DataFrame(feat_rows)

    # 偏差値化（母集団＝全体。厳密には時点ごとに分けるべきだが実用上の近似）
    for col, out in [("ten_raw", "ten_index"), ("agari_raw", "agari_index"), ("ability_raw", "ability_index")]:
        valid = df[col].notna()
        df[out] = 50.0
        if valid.any():
            df.loc[valid, out] = _devscore(df.loc[valid, col])

    # カテゴリを数値化
    df["surface_code"] = df["surface"].map({"turf": 0, "dirt": 1}).fillna(0).astype(int)
    df["turn_code"] = df["turn"].map({"left": 0, "right": 1, "straight": 2}).fillna(0).astype(int)
    df["track_cond_code"] = df["track_condition"].map({"firm": 0, "good": 1, "yielding": 2, "soft": 3}).fillna(0).astype(int)

    # 結果ラベル（学習用）
    label_df = results[["race_id", "horse_id", "finish_pos"]]
    df = df.merge(label_df, on=["race_id", "horse_id"], how="left")
    df.rename(columns={"finish_pos": "label_finish"}, inplace=True)

    return df


FEATURE_COLS = [
    "distance_m", "n_runners", "age", "weight_kg",
    "surface_code", "turn_code", "track_cond_code", "draw",
    "p_nige", "p_senko", "p_sashi", "p_oikomi",
    "ten_index", "agari_index", "ability_index",
    "dist_fit", "surface_fit", "track_cond_fit", "course_place_rate",
    "days_since_last",
]


def pace_forecast_features(df: pd.DataFrame) -> pd.DataFrame:
    """レース単位の集約: 出走馬の脚質分布・テン分布からペース予想用特徴を作る."""
    g = df.groupby("race_id")
    out = pd.DataFrame({
        "race_id": g.size().index,
        "n_nige_cand": g.apply(lambda x: (x["p_nige"] > 0.4).sum()).values,
        "n_senko_cand": g.apply(lambda x: (x["p_senko"] > 0.4).sum()).values,
        "mean_p_nige": g["p_nige"].mean().values,
        "mean_p_senko": g["p_senko"].mean().values,
        "mean_p_sashi": g["p_sashi"].mean().values,
        "mean_ten": g["ten_index"].mean().values,
        "max_ten": g["ten_index"].max().values,
        "top2_ten_mean": g["ten_index"].apply(lambda x: x.nlargest(2).mean()).values,
        "distance_m": g["distance_m"].first().values,
        "surface_code": g["surface_code"].first().values,
        "n_runners": g["n_runners"].first().values,
        "track_cond_code": g["track_cond_code"].first().values,
    })
    return out


PACE_FEATURE_COLS = [
    "n_nige_cand", "n_senko_cand", "mean_p_nige", "mean_p_senko", "mean_p_sashi",
    "mean_ten", "max_ten", "top2_ten_mean", "distance_m", "surface_code",
    "n_runners", "track_cond_code",
]
