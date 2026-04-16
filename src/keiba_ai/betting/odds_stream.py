"""オッズストリーム: 最新値の保持 + asyncio 購読者配信."""
from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime
from typing import Any


class OddsStream:
    """最新オッズを保持し、複数購読者（WebSocket等）に配信する.

    - publish(race_id, odds, ts): 新しいティックを追加
    - subscribe(race_id): async iterator として最新オッズを受け取れる
    """

    def __init__(self, history_max: int = 200):
        self._latest: dict[str, dict[str, Any]] = {}
        self._history: dict[str, list[dict]] = defaultdict(list)
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)
        self._history_max = history_max
        self._lock = asyncio.Lock()

    async def publish(self, race_id: str, odds: dict, ts: datetime | None = None) -> None:
        ts = ts or datetime.utcnow()
        payload = {"race_id": race_id, "ts": ts.isoformat(), "odds": odds}
        async with self._lock:
            self._latest[race_id] = payload
            hist = self._history[race_id]
            hist.append(payload)
            if len(hist) > self._history_max:
                del hist[: len(hist) - self._history_max]
            queues = list(self._subscribers[race_id])
        for q in queues:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass

    def latest(self, race_id: str) -> dict | None:
        return self._latest.get(race_id)

    def history(self, race_id: str) -> list[dict]:
        return list(self._history.get(race_id, []))

    async def subscribe(self, race_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        async with self._lock:
            self._subscribers[race_id].append(q)
            # 初期値を即送信
            if race_id in self._latest:
                q.put_nowait(self._latest[race_id])
        return q

    async def unsubscribe(self, race_id: str, q: asyncio.Queue) -> None:
        async with self._lock:
            if q in self._subscribers[race_id]:
                self._subscribers[race_id].remove(q)


# グローバル インスタンス
stream = OddsStream()
