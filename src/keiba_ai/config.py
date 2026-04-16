"""設定ローダ."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class DataConfig(BaseModel):
    source: str = "csv"
    csv_dir: str = "sample_data"
    history_dir: str = "data/odds_history"


class PaceClassifierConfig(BaseModel):
    num_leaves: int = 31
    learning_rate: float = 0.08
    n_estimators: int = 200
    min_data_in_leaf: int = 30


class RankerConfig(BaseModel):
    num_leaves: int = 63
    learning_rate: float = 0.05
    n_estimators: int = 400
    min_data_in_leaf: int = 50
    label_gain: list[int] = Field(default_factory=lambda: list(range(18)))


class ModelConfig(BaseModel):
    dir: str = "models"
    pace_classifier: PaceClassifierConfig = Field(default_factory=PaceClassifierConfig)
    ranker: RankerConfig = Field(default_factory=RankerConfig)


class BettingConfig(BaseModel):
    ev_threshold: float = 0.10
    kelly_fraction: float = 0.25
    stake_cap: float = 0.05
    min_stake: int = 100
    max_picks: int = 8
    allowed_tickets: list[str] = Field(
        default_factory=lambda: ["win", "place", "quinella", "exacta", "trio", "trifecta"]
    )


class LiveConfig(BaseModel):
    interval_sec_default: float = 10.0
    interval_sec_close: float = 3.0
    close_window_sec: float = 60.0


class AppConfig(BaseModel):
    data: DataConfig = Field(default_factory=DataConfig)
    model: ModelConfig = Field(default_factory=ModelConfig)
    betting: BettingConfig = Field(default_factory=BettingConfig)
    live: LiveConfig = Field(default_factory=LiveConfig)


def load_config(path: str | Path | None = None) -> AppConfig:
    """YAMLから設定を読み込む。path=Noneなら既定値."""
    if path is None:
        return AppConfig()
    p = Path(path)
    if not p.exists():
        return AppConfig()
    raw: dict[str, Any] = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return AppConfig(**raw)
