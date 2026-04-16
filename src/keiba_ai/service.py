"""予測サービス: 学習・推論・買い目推奨のオーケストレータ."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from .config import AppConfig
from .data.base import DataSource
from .data.schema import (
    Prediction,
    RacePrediction,
    RaceRecommendation,
    RunningStyle,
)
from .features.pipeline import (
    FEATURE_COLS,
    PACE_FEATURE_COLS,
    build_features,
    pace_forecast_features,
)
from .models.explainer import top_factors
from .models.pace_classifier import PACE_LABELS, PaceClassifier
from .models.ranker import ScenarioRanker
from .models.registry import ModelBundle
from .models.scenario_mix import mix_scenarios
from .betting.recommender import recommend


def _scenario_from_first3f(first3f_sec: float, distance_m: int) -> str:
    """過去レースの前半3Fタイムをシナリオラベルに分類（分位ベース: 簡易）."""
    # 距離ごとの閾値を粗く: 短距離ほど前半早い
    if distance_m <= 1400:
        if first3f_sec < 33.5:
            return "high"
        if first3f_sec < 34.7:
            return "mid"
        return "slow"
    else:
        if first3f_sec < 34.5:
            return "high"
        if first3f_sec < 35.7:
            return "mid"
        return "slow"


class PredictionService:
    """学習・推論のエントリポイント."""

    def __init__(self, source: DataSource, cfg: AppConfig | None = None):
        self.source = source
        self.cfg = cfg or AppConfig()
        self.bundle: ModelBundle | None = None

    # ---- 学習 ----
    def train(self, model_dir: str | Path | None = None) -> dict[str, float]:
        races = self.source.load_races()
        runners = self.source.load_runners()
        results = self.source.load_results()
        if races.empty or runners.empty or results.empty:
            raise RuntimeError("データが空です。サンプル生成スクリプトを実行してください。")

        # 特徴量
        feats = build_features(races, runners, results)
        # label_finish が必要
        feats = feats.dropna(subset=["label_finish"]).reset_index(drop=True)

        # ペース教師ラベルを過去走（自身の results）から作成: レース単位の first3f 平均で分類
        race_pace = (
            results.groupby("race_id")["first3f_sec"].mean().rename("race_first3f_mean").reset_index()
        )
        race_pace = race_pace.merge(races[["race_id", "distance_m"]], on="race_id", how="left")
        race_pace["pace_label"] = race_pace.apply(
            lambda r: _scenario_from_first3f(r["race_first3f_mean"], r["distance_m"]), axis=1
        )

        # ペース分類器: レース単位の特徴量
        pace_df = pace_forecast_features(feats)
        pace_df = pace_df.merge(race_pace[["race_id", "pace_label"]], on="race_id", how="inner")
        pace_model = PaceClassifier(params=self._pace_params())
        pace_model.fit(pace_df, pace_df["pace_label"])

        # シナリオ別 Ranker
        feats_with_label = feats.merge(race_pace[["race_id", "pace_label"]], on="race_id", how="left")
        ranker = ScenarioRanker(params=self._ranker_params())
        for scenario in PACE_LABELS:
            sub = feats_with_label[feats_with_label["pace_label"] == scenario]
            if len(sub) > 100:
                ranker.fit_scenario(sub, scenario)
            else:
                # データが少ないシナリオは全データで学習（フォールバック）
                ranker.fit_scenario(feats_with_label, scenario)

        bundle = ModelBundle(pace=pace_model, ranker=ranker)
        self.bundle = bundle

        out_dir = Path(model_dir or self.cfg.model.dir)
        bundle.save(out_dir)

        metrics = {
            "n_races": float(len(races)),
            "n_runners": float(len(feats)),
            "scenarios": float(len(ranker.models)),
        }
        return metrics

    def _pace_params(self) -> dict:
        pc = self.cfg.model.pace_classifier
        return {
            "objective": "multiclass",
            "num_class": 3,
            "learning_rate": pc.learning_rate,
            "num_leaves": pc.num_leaves,
            "min_data_in_leaf": pc.min_data_in_leaf,
            "n_estimators": pc.n_estimators,
            "verbose": -1,
        }

    def _ranker_params(self) -> dict:
        r = self.cfg.model.ranker
        return {
            "objective": "lambdarank",
            "metric": "ndcg",
            "ndcg_eval_at": [3, 5],
            "learning_rate": r.learning_rate,
            "num_leaves": r.num_leaves,
            "min_data_in_leaf": r.min_data_in_leaf,
            "n_estimators": r.n_estimators,
            "label_gain": r.label_gain,
            "verbose": -1,
        }

    # ---- 推論 ----
    def load(self, model_dir: str | Path | None = None) -> None:
        d = Path(model_dir or self.cfg.model.dir)
        self.bundle = ModelBundle.load(d)

    def predict_race(self, race_id: str) -> RacePrediction:
        assert self.bundle is not None, "Call load() first"
        races = self.source.load_races()
        runners = self.source.load_runners()
        results = self.source.load_results()
        # 対象レースのみ特徴量化（全レース回すと O(N) で重い）
        feats = build_features(races, runners, results, target_race_ids=[race_id]).reset_index(drop=True)
        if feats.empty:
            raise ValueError(f"race_id={race_id} の出走馬が見つかりません")

        # 【重要】推論時は、その馬の過去走に「今回レース自身」が含まれないよう
        # build_features 内で `race_date` より前に絞り込んでいる前提。
        # ただし今回は同レースのラベルは NaN (未開催) を想定するので、
        # 過去走集計では当日開催以前が含まれうるのが厳密ではないが、
        # races.post_time を race_date より後にすることで回避できる。

        # pace予測
        pace_df = pace_forecast_features(feats)
        pace_probs = self.bundle.pace.predict_dict(pace_df)[0]

        # シナリオ別 scores
        scores_by = {}
        for sc in PACE_LABELS:
            scores_by[sc] = self.bundle.ranker.predict_scores(feats, sc)

        mixed = mix_scenarios(scores_by, pace_probs)

        # 根拠（説明）
        # 代表スコア: pace_probs で重み付け平均
        rep_scores = np.zeros(len(feats))
        for sc, p in pace_probs.items():
            rep_scores += p * scores_by[sc]
        factors_list = top_factors(feats, rep_scores, top_k=4)

        # 脚質推定（直近の確率分布から argmax）
        style_map = {"nige": RunningStyle.NIGE, "senko": RunningStyle.SENKO,
                     "sashi": RunningStyle.SASHI, "oikomi": RunningStyle.OIKOMI}

        runners_name = runners.set_index(["race_id", "horse_id"])["horse_name"].to_dict()

        preds: list[Prediction] = []
        for i, row in feats.iterrows():
            styles = {
                "nige": row["p_nige"], "senko": row["p_senko"],
                "sashi": row["p_sashi"], "oikomi": row["p_oikomi"],
            }
            style_key = max(styles, key=styles.get)
            preds.append(Prediction(
                race_id=race_id,
                horse_no=int(row["horse_no"]),
                horse_name=runners_name.get((race_id, row["horse_id"]), ""),
                score=float(rep_scores[i]),
                p_win=float(mixed["p1"][i]),
                p_2nd=float(mixed["p2"][i]),
                p_3rd=float(mixed["p3"][i]),
                p_place=float(mixed["place"][i]),
                ten_index=float(row["ten_index"]),
                agari_index=float(row["agari_index"]),
                running_style=style_map[style_key],
                top_factors=factors_list[i],
            ))

        # P(1着)の降順で並べ替え
        preds.sort(key=lambda p: p.p_win, reverse=True)

        return RacePrediction(
            race_id=race_id,
            pace_prob=pace_probs,
            runners=preds,
            computed_at=datetime.utcnow(),
        )

    # ---- 買い目 ----
    def recommend_bets(
        self,
        race_id: str,
        budget: int,
        odds: dict,
        *,
        prediction: RacePrediction | None = None,
    ) -> RaceRecommendation:
        pred = prediction or self.predict_race(race_id)
        horse_nos = [p.horse_no for p in pred.runners]
        # Predictionは p_win 降順になっているが、入力scoreも保持しているのでそのまま使える
        scores = np.array([p.score for p in pred.runners])
        p1 = np.array([p.p_win for p in pred.runners])
        place = np.array([p.p_place for p in pred.runners])

        return recommend(
            race_id=race_id,
            horse_nos=horse_nos,
            scores=scores,
            p1=p1,
            place_prob=place,
            odds=odds,
            budget=budget,
            cfg=self.cfg.betting,
        )
