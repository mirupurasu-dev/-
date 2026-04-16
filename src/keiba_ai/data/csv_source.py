"""CSV DataSource 実装."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .base import DataSource


class CsvDataSource(DataSource):
    """指定ディレクトリ内の races.csv / runners.csv / results.csv / odds.csv を読む."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def _read(self, name: str) -> pd.DataFrame:
        path = self.root / f"{name}.csv"
        if not path.exists():
            return pd.DataFrame()
        return pd.read_csv(path)

    def load_races(self) -> pd.DataFrame:
        df = self._read("races")
        if df.empty:
            return df
        df["date"] = pd.to_datetime(df["date"])
        df["post_time"] = pd.to_datetime(df["post_time"])
        return df

    def load_runners(self) -> pd.DataFrame:
        return self._read("runners")

    def load_results(self) -> pd.DataFrame:
        return self._read("results")

    def load_odds(self) -> pd.DataFrame:
        return self._read("odds")
