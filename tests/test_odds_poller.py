import asyncio

import pytest

from keiba_ai.betting.odds_poller import MockOddsBackend, poll_odds
from keiba_ai.betting.odds_stream import OddsStream


@pytest.mark.asyncio
async def test_mock_poller_publishes_ticks():
    base = {
        "win": {1: 3.0, 2: 5.0, 3: 10.0},
        "place": {1: (1.3, 1.5), 2: (1.8, 2.1), 3: (3.0, 4.0)},
        "quinella": {"1-2": 12.0},
        "exacta": {},
        "trio": {},
        "trifecta": {},
    }
    backend = MockOddsBackend(base, volatility=0.1, seed=123)
    stream = OddsStream()
    await poll_odds("R1", backend, stream, interval_sec=0.01, max_ticks=3)
    hist = stream.history("R1")
    assert len(hist) >= 1
    # 変動が発生している（ハッシュ差分で1以上配信される）
    latest = stream.latest("R1")
    assert latest is not None
    assert "win" in latest["odds"]


@pytest.mark.asyncio
async def test_hash_dedup_no_volatility():
    base = {"win": {1: 3.0}, "place": {}, "quinella": {}, "exacta": {}, "trio": {}, "trifecta": {}}
    backend = MockOddsBackend(base, volatility=0.0, seed=1)
    stream = OddsStream()
    await poll_odds("R2", backend, stream, interval_sec=0.01, max_ticks=5)
    hist = stream.history("R2")
    # volatility=0 なら毎tick同じ値 → 初回のみpublish
    assert len(hist) == 1
