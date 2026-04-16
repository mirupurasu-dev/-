"""サンプル（合成）データ生成スクリプト.

競馬ロジックに沿って、脚質・テン力・上がり力・距離適性などの潜在変数を持つ
仮想の馬・レースを生成し、races.csv / runners.csv / results.csv / odds.csv
を `sample_data/` に書き出す。

・展開（前半ペース）は逃げ馬のテン力から確率的に決まる
・着順は「展開適合度 + 適性 + 枠バイアス + ノイズ」で決まる
・オッズは人気に概ね連動するが、過小/過大評価が混じるよう歪める
これによりモデルが学習する余地（回収率プラスの買い目）を残す。
"""
from __future__ import annotations

import argparse
import hashlib
import random
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

COURSES = ["東京", "中山", "阪神", "京都", "中京", "新潟", "福島", "小倉", "札幌", "函館"]
STYLES = ["nige", "senko", "sashi", "oikomi"]


def _seed_rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)


def _hash_int(s: str, mod: int) -> int:
    return int(hashlib.md5(s.encode()).hexdigest(), 16) % mod


def generate_horses(rng: np.random.Generator, n: int = 2500) -> pd.DataFrame:
    """競走馬マスタ。潜在変数: 実力・テン・上がり・脚質傾向・距離適性."""
    horses = []
    for i in range(n):
        horse_id = f"H{i:05d}"
        ability = rng.normal(0, 1)          # 総合実力
        ten_talent = rng.normal(0, 1)       # 先行力
        agari_talent = rng.normal(0, 1)     # 末脚
        # 脚質傾向はテン/上がりから決定的に（逃げ型ほどテン高・上がり並）
        if ten_talent > 0.8:
            style = "nige"
        elif ten_talent > 0.2:
            style = "senko"
        elif agari_talent > 0.2:
            style = "sashi"
        else:
            style = "oikomi"
        dist_pref = int(rng.choice([1200, 1400, 1600, 1800, 2000, 2400]))
        surface_pref = rng.choice(["turf", "dirt"], p=[0.7, 0.3])
        horses.append({
            "horse_id": horse_id,
            "horse_name": f"サンプル{i:05d}",
            "ability": ability,
            "ten_talent": ten_talent,
            "agari_talent": agari_talent,
            "style": style,
            "dist_pref": dist_pref,
            "surface_pref": surface_pref,
        })
    return pd.DataFrame(horses)


def generate_races(
    rng: np.random.Generator,
    horses: pd.DataFrame,
    n_races: int = 2000,
    start_date: datetime = datetime(2022, 1, 1),
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """レース・出走・結果・確定オッズを生成."""
    races_rows, runners_rows, results_rows, odds_rows = [], [], [], []

    for r in range(n_races):
        race_id = f"R{r:06d}"
        date = start_date + timedelta(days=r // 12, hours=(r % 12))
        course = rng.choice(COURSES)
        distance_m = int(rng.choice([1200, 1400, 1600, 1800, 2000, 2400]))
        surface = rng.choice(["turf", "dirt"], p=[0.7, 0.3])
        turn = rng.choice(["left", "right"])
        track_cond = rng.choice(["firm", "good", "yielding", "soft"], p=[0.6, 0.25, 0.1, 0.05])
        n_runners = int(rng.integers(8, 17))

        # ランダムに出走馬を抽選
        field = horses.sample(n=n_runners, random_state=rng.integers(0, 10**9)).reset_index(drop=True)
        field = field.copy()
        field["horse_no"] = np.arange(1, n_runners + 1)
        field["draw"] = np.ceil(field["horse_no"] / 2).astype(int)  # 2馬ずつ枠

        post_time = date + timedelta(minutes=30 * (r % 12))
        races_rows.append({
            "race_id": race_id,
            "date": date.isoformat(),
            "course": course,
            "race_no": (r % 12) + 1,
            "race_name": f"サンプル{r%12+1}R",
            "distance_m": distance_m,
            "surface": surface,
            "turn": turn,
            "track_condition": track_cond,
            "n_runners": n_runners,
            "post_time": post_time.isoformat(),
        })

        # --- 展開（前半ペース）の決定 ---
        # 逃げ馬のテン力合計が高い = ハイペース寄り
        nige_senko = field[field["style"].isin(["nige", "senko"])]
        pace_score = nige_senko["ten_talent"].sum() if len(nige_senko) else 0.0
        pace_score += rng.normal(0, 1.2)
        if pace_score > 2.5:
            pace_label = "high"
        elif pace_score > -0.5:
            pace_label = "mid"
        else:
            pace_label = "slow"

        # --- 馬ごとの走破タイム決定（潜在変数→着順） ---
        # 基準タイム（距離×馬場）
        base_time = distance_m * 0.062 + (20.0 if surface == "dirt" else 18.0)
        if track_cond == "good":
            base_time += 0.6
        elif track_cond == "yielding":
            base_time += 1.5
        elif track_cond == "soft":
            base_time += 2.5

        # 展開適合度（ハイ=差し有利、スロー=前有利）
        style_adj = {
            "high":  {"nige": +0.6, "senko": +0.2, "sashi": -0.3, "oikomi": -0.5},
            "mid":   {"nige": +0.0, "senko": -0.1, "sashi": -0.1, "oikomi": +0.0},
            "slow":  {"nige": -0.6, "senko": -0.3, "sashi": +0.3, "oikomi": +0.5},
        }
        # 注: ハイペース時は逃げ/先行に+ (遅れやすい) = タイム悪化方向なので符号反転
        # style_adj は「タイム加算（悪化）」として扱う

        # 距離適性
        dist_penalty = np.abs(field["dist_pref"].to_numpy() - distance_m) / 800.0  # ±0.2〜0.6

        # 枠順バイアス（内枠が基本的にわずか有利）
        draw_penalty = (field["draw"].to_numpy() - 4.5) * 0.02

        # 馬場適性
        surf_penalty = np.where(field["surface_pref"].to_numpy() != surface, 0.5, 0.0)

        # 展開加算
        pace_penalty = field["style"].map(style_adj[pace_label]).to_numpy()

        # テン/上がり talent の効き方（シナリオ依存）
        # ハイペース: agari_talent が効く、テンは効きにくい（潰される）
        # スロー:     ten_talent が効く（前残り）
        if pace_label == "high":
            talent_contrib = -0.6 * field["agari_talent"].to_numpy() - 0.1 * field["ten_talent"].to_numpy()
        elif pace_label == "slow":
            talent_contrib = -0.1 * field["agari_talent"].to_numpy() - 0.5 * field["ten_talent"].to_numpy()
        else:
            talent_contrib = -0.3 * field["agari_talent"].to_numpy() - 0.3 * field["ten_talent"].to_numpy()

        ability_contrib = -0.7 * field["ability"].to_numpy()

        noise = rng.normal(0, 0.8, size=n_runners)

        finish_time = (
            base_time
            + ability_contrib
            + talent_contrib
            + pace_penalty
            + dist_penalty
            + draw_penalty
            + surf_penalty
            + noise
        )

        order = np.argsort(finish_time)
        finish_pos = np.empty(n_runners, dtype=int)
        finish_pos[order] = np.arange(1, n_runners + 1)

        # 上がり3Fタイム（馬ごと）
        base_last3f = 11.5 + (1.5 if surface == "dirt" else 0.0)
        last3f = (
            base_last3f
            - 0.6 * field["agari_talent"].to_numpy()
            + (0.3 if pace_label == "slow" else (-0.3 if pace_label == "high" else 0.0))
            + rng.normal(0, 0.25, size=n_runners)
        )
        last3f = np.clip(last3f, 10.2, 14.0)

        # 前半3F（全体ペースに連動 + 先行型ほど早い）
        pace_base = {"high": 33.0, "mid": 34.2, "slow": 35.5}[pace_label]
        style_to_ten = {"nige": -0.4, "senko": -0.2, "sashi": +0.2, "oikomi": +0.5}
        first3f = (
            pace_base
            + field["style"].map(style_to_ten).to_numpy()
            - 0.2 * field["ten_talent"].to_numpy()
            + rng.normal(0, 0.25, size=n_runners)
        )

        # コーナー通過順（脚質から生成）
        corner1 = {}
        style_to_corner = {"nige": 1.5, "senko": 4.0, "sashi": 9.0, "oikomi": 13.0}
        for i in range(n_runners):
            s = field.iloc[i]["style"]
            c = int(np.clip(style_to_corner[s] + rng.normal(0, 1.5), 1, n_runners))
            corner1[i] = c

        # 人気とオッズ（ただし多少歪める＝回収率プラスの余地を残す）
        ability_arr = field["ability"].to_numpy()
        score_est = ability_arr + rng.normal(0, 0.5, n_runners)  # 市場評価ノイズ
        # softmax で単勝確率 → オッズ（控除率20%）
        p = np.exp(score_est * 0.9)
        p = p / p.sum()
        win_odds = (1.0 - 0.20) / np.maximum(p, 1e-6)
        popularity = np.argsort(-p).argsort() + 1  # 人気（降順ランク）

        for i in range(n_runners):
            row = field.iloc[i]
            runners_rows.append({
                "race_id": race_id,
                "horse_id": row["horse_id"],
                "horse_name": row["horse_name"],
                "horse_no": int(row["horse_no"]),
                "draw": int(row["draw"]),
                "age": int(rng.integers(3, 7)),
                "sex": "M",
                "weight_kg": float(rng.normal(470, 20)),
                "jockey_id": f"J{_hash_int(row['horse_id'], 500):04d}",
                "jockey_name": "",
                "trainer_id": f"T{_hash_int(row['horse_id'], 200):03d}",
                "sire_id": f"S{_hash_int(row['horse_id']+'S', 300):03d}",
                "dam_sire_id": f"DS{_hash_int(row['horse_id']+'DS', 300):03d}",
            })
            results_rows.append({
                "race_id": race_id,
                "horse_id": row["horse_id"],
                "finish_pos": int(finish_pos[i]),
                "finish_time_sec": float(finish_time[i]),
                "last3f_sec": float(last3f[i]),
                "first3f_sec": float(first3f[i]),
                "corner1": int(corner1[i]),
                "corner2": int(corner1[i]),
                "corner3": int(corner1[i]) if n_runners > 0 else 0,
                "corner4": int(np.clip(corner1[i] + rng.integers(-2, 3), 1, n_runners)),
                "popularity": int(popularity[i]),
                "win_odds": float(win_odds[i]),
                "pace_label": pace_label,  # 教師用（後で分離可）
            })
            odds_rows.append({
                "race_id": race_id,
                "horse_no": int(row["horse_no"]),
                "win": float(win_odds[i]),
                "place_low": float(max(1.0, win_odds[i] * 0.35)),
                "place_high": float(max(1.1, win_odds[i] * 0.6)),
            })

    races_df = pd.DataFrame(races_rows)
    runners_df = pd.DataFrame(runners_rows)
    results_df = pd.DataFrame(results_rows)
    odds_df = pd.DataFrame(odds_rows)
    return races_df, runners_df, results_df, odds_df


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="sample_data", help="出力ディレクトリ")
    parser.add_argument("--n-races", type=int, default=1500)
    parser.add_argument("--n-horses", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = _seed_rng(args.seed)
    random.seed(args.seed)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    horses = generate_horses(rng, n=args.n_horses)
    races, runners, results, odds = generate_races(rng, horses, n_races=args.n_races)

    races.to_csv(out / "races.csv", index=False)
    runners.to_csv(out / "runners.csv", index=False)
    results.to_csv(out / "results.csv", index=False)
    odds.to_csv(out / "odds.csv", index=False)
    horses[["horse_id", "horse_name"]].to_csv(out / "horses.csv", index=False)
    print(f"Wrote {len(races)} races, {len(runners)} runners, {len(results)} results to {out}/")


if __name__ == "__main__":
    main()
