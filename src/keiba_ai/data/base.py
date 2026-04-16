"""DataSource 抽象基底."""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class DataSource(ABC):
    """過去データを DataFrame として提供する抽象基底.

    races_df:   race_id, date, course, race_no, distance_m, surface, turn,
                track_condition, n_runners, post_time
    runners_df: race_id, horse_id, horse_no, draw, age, sex, weight_kg,
                jockey_id, trainer_id, sire_id, dam_sire_id
    results_df: race_id, horse_id, finish_pos, finish_time_sec, last3f_sec,
                first3f_sec, corner1, corner2, corner3, corner4,
                popularity, win_odds
    odds_df:    race_id, horse_no, win, place_low, place_high
                （過去の確定オッズ用）
    """

    @abstractmethod
    def load_races(self) -> pd.DataFrame: ...

    @abstractmethod
    def load_runners(self) -> pd.DataFrame: ...

    @abstractmethod
    def load_results(self) -> pd.DataFrame: ...

    @abstractmethod
    def load_odds(self) -> pd.DataFrame: ...
