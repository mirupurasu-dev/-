"""Pydantic スキーマ: レース・馬・結果・オッズ."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class Surface(str, Enum):
    TURF = "turf"      # 芝
    DIRT = "dirt"      # ダート


class TrackCondition(str, Enum):
    FIRM = "firm"      # 良
    GOOD = "good"      # 稍重
    YIELDING = "yielding"  # 重
    SOFT = "soft"      # 不良


class TurnDirection(str, Enum):
    LEFT = "left"      # 左回り
    RIGHT = "right"    # 右回り
    STRAIGHT = "straight"


class RunningStyle(str, Enum):
    NIGE = "nige"          # 逃げ
    SENKO = "senko"        # 先行
    SASHI = "sashi"        # 差し
    OIKOMI = "oikomi"      # 追込


class TicketType(str, Enum):
    WIN = "win"              # 単勝
    PLACE = "place"          # 複勝
    QUINELLA = "quinella"    # 馬連
    EXACTA = "exacta"        # 馬単
    TRIO = "trio"            # 3連複
    TRIFECTA = "trifecta"    # 3連単


class Race(BaseModel):
    """レース基本情報."""
    race_id: str
    date: datetime
    course: str               # 競馬場（東京/中山/阪神/京都/…）
    race_no: int
    race_name: str = ""
    distance_m: int
    surface: Surface
    turn: TurnDirection
    track_condition: TrackCondition = TrackCondition.FIRM
    n_runners: int
    post_time: datetime       # 発走時刻


class Runner(BaseModel):
    """出走馬."""
    race_id: str
    horse_id: str
    horse_name: str = ""
    horse_no: int             # 馬番
    draw: int                 # 枠番
    age: int
    sex: str = "M"
    weight_kg: float
    jockey_id: str = ""
    jockey_name: str = ""
    trainer_id: str = ""
    sire_id: str = ""         # 父
    dam_sire_id: str = ""     # 母父


class Result(BaseModel):
    """レース結果（過去走用）."""
    race_id: str
    horse_id: str
    finish_pos: int           # 着順（失格等は99）
    finish_time_sec: float    # 走破タイム(秒)
    last3f_sec: float         # 上がり3F(秒)
    first3f_sec: float | None = None  # 前半3F（算出可能なら）
    corner_passes: list[int] = Field(default_factory=list)  # 各コーナー通過順位
    margin_lengths: float = 0.0
    popularity: int = 0
    win_odds: float = 0.0


class Odds(BaseModel):
    """単一ティックのオッズ（複数券種をまとめて保持）."""
    race_id: str
    ts: datetime
    win: dict[int, float] = Field(default_factory=dict)        # 馬番→倍率
    place: dict[int, tuple[float, float]] = Field(default_factory=dict)  # 下限・上限
    quinella: dict[str, float] = Field(default_factory=dict)   # "i-j" (i<j)
    exacta: dict[str, float] = Field(default_factory=dict)     # "i->j"
    trio: dict[str, float] = Field(default_factory=dict)       # "i-j-k" (ソート済)
    trifecta: dict[str, float] = Field(default_factory=dict)   # "i->j->k"


class Prediction(BaseModel):
    """1レースの予測結果（馬別）."""
    race_id: str
    horse_no: int
    horse_name: str = ""
    score: float              # シナリオ合成後のスコア
    p_win: float              # P(1着)
    p_2nd: float              # P(2着)
    p_3rd: float              # P(3着)
    p_place: float            # P(複勝圏)
    ten_index: float = 50.0   # テン偏差値
    agari_index: float = 50.0 # 上がり偏差値
    running_style: RunningStyle = RunningStyle.SENKO
    top_factors: list[tuple[str, float]] = Field(default_factory=list)  # (要因名, 寄与)


class RacePrediction(BaseModel):
    """レース全体の予測."""
    race_id: str
    pace_prob: dict[str, float]   # {"high":0.3, "mid":0.5, "slow":0.2}
    runners: list[Prediction]
    computed_at: datetime


class BetRecommendation(BaseModel):
    """買い目推奨."""
    ticket: TicketType
    selection: str            # "3" or "3-5" or "3-5-7" など
    odds: float               # その時点のオッズ
    probability: float        # 理論的中確率
    expected_value: float     # EV = odds*p - 1
    kelly_fraction: float     # 推奨掛け率（資金に対して）
    stake: int                # 推奨金額（円、100円刻み）


class RaceRecommendation(BaseModel):
    """レースの推奨買い目一式."""
    race_id: str
    budget: int
    picks: list[BetRecommendation]
    total_stake: int
    expected_profit: float
    computed_at: datetime
