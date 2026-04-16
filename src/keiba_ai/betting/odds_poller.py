"""オッズポーラ: 一定間隔でバックエンドから取得して Stream に配信.

バックエンドは `OddsBackend` プロトコル:
- async def fetch(race_id) -> dict    # 辞書形式のオッズ
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import random
from datetime import datetime
from typing import Protocol

from ..config import LiveConfig
from .odds_stream import OddsStream


class OddsBackend(Protocol):
    async def fetch(self, race_id: str) -> dict: ...
    async def close(self) -> None: ...


class MockOddsBackend:
    """ベースオッズ（直近の確定 or 推定）からランダムに揺らす.

    Args:
        base_odds: {"win":{...},"place":...,"quinella":...,...}
        volatility: 揺れ幅。0.05 なら ±5% 程度
    """

    def __init__(self, base_odds: dict, volatility: float = 0.05, seed: int | None = None):
        self.base = base_odds
        self.vol = volatility
        self.rng = random.Random(seed)

    async def fetch(self, race_id: str) -> dict:
        # ±vol の範囲でランダムウォーク（再現性のためseed入りrngは使わず毎tickずらす）
        def jitter(v: float) -> float:
            factor = 1.0 + self.rng.uniform(-self.vol, self.vol)
            return max(1.0, round(v * factor, 1))

        new = {}
        for ticket, items in self.base.items():
            if ticket == "place":
                new["place"] = {
                    int(k): (jitter(v[0]), jitter(v[1])) for k, v in items.items()
                }
            elif ticket == "win":
                new["win"] = {int(k): jitter(v) for k, v in items.items()}
            else:
                new[ticket] = {k: jitter(v) for k, v in items.items()}
        return new

    async def close(self) -> None:
        return


def _hash(obj: dict) -> str:
    return hashlib.md5(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


async def poll_odds(
    race_id: str,
    backend: OddsBackend,
    stream: OddsStream,
    *,
    interval_sec: float = 10.0,
    max_ticks: int | None = None,
    stop_event: asyncio.Event | None = None,
    post_time: datetime | None = None,
    live_cfg: LiveConfig | None = None,
) -> None:
    """race_id のオッズを interval_sec ごとにポーリングして stream に配信.

    - ハッシュ差分チェックで無変化はスキップ
    - post_time があれば発走 close_window_sec 前で間隔を短縮
    """
    cfg = live_cfg or LiveConfig()
    stop_event = stop_event or asyncio.Event()
    last_hash: str | None = None
    ticks = 0

    try:
        while not stop_event.is_set():
            # 発走時刻超過で自動停止
            if post_time and datetime.utcnow() >= post_time:
                break

            # ポーリング間隔（発走近いほど短く）
            cur_interval = interval_sec
            if post_time:
                seconds_to_post = (post_time - datetime.utcnow()).total_seconds()
                if 0 < seconds_to_post <= cfg.close_window_sec:
                    cur_interval = cfg.interval_sec_close

            try:
                odds = await backend.fetch(race_id)
            except Exception:
                await asyncio.sleep(cur_interval)
                continue

            h = _hash(odds)
            if h != last_hash:
                await stream.publish(race_id, odds)
                last_hash = h

            ticks += 1
            if max_ticks is not None and ticks >= max_ticks:
                break

            try:
                await asyncio.wait_for(stop_event.wait(), timeout=cur_interval)
            except asyncio.TimeoutError:
                pass
    finally:
        await backend.close()
