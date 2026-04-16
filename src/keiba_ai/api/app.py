"""FastAPI エントリ: REST + WebSocket ライブ配信."""
from __future__ import annotations

import asyncio
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from ..betting.odds_poller import MockOddsBackend, poll_odds
from ..betting.odds_stream import stream
from ..betting.recommender import enumerate_all_tickets
from ..config import AppConfig, load_config
from ..data.csv_source import CsvDataSource
from ..service import PredictionService


def _load_cfg() -> AppConfig:
    cfg_path = os.getenv("KEIBA_CONFIG", "config/config.yaml")
    return load_config(cfg_path)


def _load_service() -> PredictionService:
    cfg = _load_cfg()
    src = CsvDataSource(cfg.data.csv_dir)
    svc = PredictionService(src, cfg)
    model_dir = Path(cfg.model.dir)
    if (model_dir / "pace_classifier.joblib").exists():
        svc.load(model_dir)
    return svc


app = FastAPI(title="競馬予想AI API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_poller_tasks: dict[str, asyncio.Task] = {}
_poller_stops: dict[str, asyncio.Event] = {}


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "ts": datetime.utcnow().isoformat()}


@app.get("/api/races/today")
def races_today():
    cfg = _load_cfg()
    src = CsvDataSource(cfg.data.csv_dir)
    races = src.load_races()
    runners = src.load_runners()
    if races.empty:
        return {"races": []}
    # サンプルデータは「当日」が曖昧なので、最新日付のレースを返す
    latest = pd.to_datetime(races["date"]).max()
    target_day = races[pd.to_datetime(races["date"]).dt.date == latest.date()]
    out = []
    for _, r in target_day.iterrows():
        rid = r["race_id"]
        nrun = int((runners["race_id"] == rid).sum())
        out.append({
            "race_id": rid,
            "course": r["course"],
            "race_no": int(r["race_no"]),
            "race_name": r.get("race_name", ""),
            "distance_m": int(r["distance_m"]),
            "surface": r["surface"],
            "track_condition": r["track_condition"],
            "n_runners": nrun,
            "post_time": str(r["post_time"]),
        })
    out.sort(key=lambda x: x["post_time"])
    return {"races": out}


@app.get("/api/races/{race_id}")
def race_detail(race_id: str):
    cfg = _load_cfg()
    src = CsvDataSource(cfg.data.csv_dir)
    races = src.load_races()
    runners = src.load_runners()
    rr = races[races["race_id"] == race_id]
    if rr.empty:
        raise HTTPException(404, "race not found")
    r = rr.iloc[0]
    rn = runners[runners["race_id"] == race_id].sort_values("horse_no")
    return {
        "race_id": race_id,
        "course": r["course"],
        "race_no": int(r["race_no"]),
        "race_name": r.get("race_name", ""),
        "distance_m": int(r["distance_m"]),
        "surface": r["surface"],
        "turn": r["turn"],
        "track_condition": r["track_condition"],
        "n_runners": int(r["n_runners"]),
        "post_time": str(r["post_time"]),
        "runners": rn.to_dict(orient="records"),
    }


@app.get("/api/predict/{race_id}")
def predict(race_id: str):
    svc = _load_service()
    if svc.bundle is None:
        raise HTTPException(503, "model not trained yet. run `keiba train` first.")
    try:
        pred = svc.predict_race(race_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return pred.model_dump()


def _build_base_odds_from_csv(race_id: str, cfg: AppConfig) -> dict:
    """確定 win/place オッズから全券種の初期値を作る（Mock用）."""
    src = CsvDataSource(cfg.data.csv_dir)
    odds_df = src.load_odds()
    runners = src.load_runners()
    row_odds = odds_df[odds_df["race_id"] == race_id]
    rn = runners[runners["race_id"] == race_id].sort_values("horse_no")
    horse_nos = rn["horse_no"].astype(int).tolist()

    win = {int(r["horse_no"]): float(r["win"]) for _, r in row_odds.iterrows()}
    place = {int(r["horse_no"]): (float(r["place_low"]), float(r["place_high"])) for _, r in row_odds.iterrows()}

    # 他券種: 単勝オッズから合成（単純なPL風 with JRA 控除）
    import math
    probs = {no: 1.0 / max(win.get(no, 99.0), 1.01) for no in horse_nos}
    s = sum(probs.values()) or 1.0
    norm = {k: v / s for k, v in probs.items()}

    def pl_pair(i: int, j: int) -> float:
        wi, wj = norm[i], norm[j]
        return wi * (wj / max(1 - wi, 1e-6)) + wj * (wi / max(1 - wj, 1e-6))

    quinella = {}
    exacta = {}
    trio = {}
    trifecta = {}
    for a, b in _pairs(horse_nos):
        p = pl_pair(a, b)
        if p > 0:
            quinella[f"{a}-{b}"] = round(0.75 / p, 1)
    for a in horse_nos:
        for b in horse_nos:
            if a == b:
                continue
            p = norm[a] * (norm[b] / max(1 - norm[a], 1e-6))
            if p > 0:
                exacta[f"{a}->{b}"] = round(0.75 / p, 1)
    from itertools import combinations, permutations
    for a, b, c in combinations(horse_nos, 3):
        # モンテカルロ相当の簡易計算（full PL 三重和）
        p = 0.0
        for x, y, z in permutations((a, b, c), 3):
            wx, wy, wz = norm[x], norm[y], norm[z]
            rem1 = max(1 - wx, 1e-6)
            rem2 = max(1 - wx - wy, 1e-6)
            p += wx * (wy / rem1) * (wz / rem2)
        if p > 0:
            trio[f"{a}-{b}-{c}"] = round(0.75 / p, 1)
    # 3連単は計算コスト高いので頭数が多いときは単純スキップ
    if len(horse_nos) <= 12:
        for x, y, z in permutations(horse_nos, 3):
            wx, wy, wz = norm[x], norm[y], norm[z]
            rem1 = max(1 - wx, 1e-6)
            rem2 = max(1 - wx - wy, 1e-6)
            p = wx * (wy / rem1) * (wz / rem2)
            if p > 0:
                trifecta[f"{x}->{y}->{z}"] = round(0.75 / p, 1)

    return {
        "win": win,
        "place": place,
        "quinella": quinella,
        "exacta": exacta,
        "trio": trio,
        "trifecta": trifecta,
    }


def _pairs(xs):
    for i in range(len(xs)):
        for j in range(i + 1, len(xs)):
            yield xs[i], xs[j]


@app.get("/api/recommend/{race_id}")
def recommend_api(race_id: str, budget: int = 10000):
    svc = _load_service()
    cfg = svc.cfg
    if svc.bundle is None:
        raise HTTPException(503, "model not trained yet. run `keiba train` first.")
    pred = svc.predict_race(race_id)
    latest = stream.latest(race_id)
    if latest:
        odds = latest["odds"]
    else:
        odds = _build_base_odds_from_csv(race_id, cfg)
    rec = svc.recommend_bets(race_id, budget=budget, odds=odds, prediction=pred)
    return {
        "prediction": pred.model_dump(),
        "recommendation": rec.model_dump(),
        "odds_ts": latest["ts"] if latest else None,
    }


@app.post("/api/live/start/{race_id}")
async def start_live(race_id: str, interval_sec: float = 10.0):
    """指定レースのオッズポーラを起動 (Mock)."""
    if race_id in _poller_tasks and not _poller_tasks[race_id].done():
        return {"status": "already_running"}
    cfg = _load_cfg()
    base = _build_base_odds_from_csv(race_id, cfg)
    backend = MockOddsBackend(base, volatility=0.04)
    stop = asyncio.Event()
    _poller_stops[race_id] = stop
    task = asyncio.create_task(
        poll_odds(race_id, backend, stream, interval_sec=interval_sec, stop_event=stop, live_cfg=cfg.live)
    )
    _poller_tasks[race_id] = task
    return {"status": "started", "interval_sec": interval_sec}


@app.post("/api/live/stop/{race_id}")
async def stop_live(race_id: str):
    stop = _poller_stops.get(race_id)
    if stop:
        stop.set()
    return {"status": "stopped"}


@app.websocket("/ws/live/{race_id}")
async def ws_live(ws: WebSocket, race_id: str):
    """オッズ・EV・買い目をリアルタイム配信."""
    await ws.accept()
    # sync 重処理はスレッドへ逃がしてイベントループを止めない
    svc = await asyncio.to_thread(_load_service)
    cfg = svc.cfg

    q = await stream.subscribe(race_id)
    try:
        if stream.latest(race_id) is None:
            base = await asyncio.to_thread(_build_base_odds_from_csv, race_id, cfg)
            await stream.publish(race_id, base)

        while True:
            payload = await q.get()
            pred = None
            rec = None
            if svc.bundle:
                try:
                    pred = await asyncio.to_thread(svc.predict_race, race_id)
                except Exception:
                    pred = None
                if pred:
                    try:
                        rec = await asyncio.to_thread(
                            svc.recommend_bets, race_id, 10000, payload["odds"], prediction=pred
                        )
                    except Exception:
                        rec = None
            msg = {
                "type": "tick",
                "race_id": race_id,
                "ts": payload["ts"],
                "odds": payload["odds"],
                "prediction": pred.model_dump(mode="json") if pred else None,
                "recommendation": rec.model_dump(mode="json") if rec else None,
            }
            await ws.send_json(msg)
    except WebSocketDisconnect:
        pass
    finally:
        await stream.unsubscribe(race_id, q)
