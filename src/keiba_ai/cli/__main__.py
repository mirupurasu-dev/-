"""`keiba` CLI エントリ."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from ..api.app import _build_base_odds_from_csv
from ..betting.odds_poller import MockOddsBackend, poll_odds
from ..betting.odds_stream import OddsStream
from ..config import load_config
from ..data.csv_source import CsvDataSource
from ..service import PredictionService

app = typer.Typer(add_completion=False, help="競馬予想AI CLI")
console = Console()


def _load(cfg_path: Path | None):
    cfg = load_config(cfg_path)
    src = CsvDataSource(cfg.data.csv_dir)
    svc = PredictionService(src, cfg)
    return cfg, svc


@app.command()
def train(
    config: Path = typer.Option(Path("config/config.yaml"), help="設定ファイル"),
    model_dir: Path = typer.Option(Path("models"), help="モデル保存先"),
):
    """学習: ペース分類器 + シナリオ別 LambdaRank."""
    cfg, svc = _load(config)
    rprint("[bold]学習を開始します...[/bold]")
    metrics = svc.train(model_dir=model_dir)
    rprint(f"[green]完了[/green] metrics={metrics}")


@app.command()
def predict(
    race_id: str = typer.Argument(..., help="予測対象のレースID"),
    config: Path = typer.Option(Path("config/config.yaml")),
    model_dir: Path = typer.Option(Path("models")),
):
    """1レースの着順確率を表示."""
    cfg, svc = _load(config)
    svc.load(model_dir)
    pred = svc.predict_race(race_id)

    rprint(f"[bold]レース {race_id}[/bold]  想定ペース: {pred.pace_prob}")
    table = Table(show_lines=False)
    table.add_column("馬番", justify="right")
    table.add_column("馬名")
    table.add_column("脚質")
    table.add_column("P(1着)", justify="right")
    table.add_column("P(2着)", justify="right")
    table.add_column("P(3着)", justify="right")
    table.add_column("P(複勝)", justify="right")
    table.add_column("テン", justify="right")
    table.add_column("上がり", justify="right")
    for p in pred.runners:
        table.add_row(
            str(p.horse_no), p.horse_name, p.running_style.value,
            f"{p.p_win*100:5.1f}%", f"{p.p_2nd*100:5.1f}%", f"{p.p_3rd*100:5.1f}%",
            f"{p.p_place*100:5.1f}%", f"{p.ten_index:.1f}", f"{p.agari_index:.1f}",
        )
    console.print(table)


@app.command()
def recommend(
    race_id: str = typer.Argument(...),
    budget: int = typer.Option(10000, help="予算（円）"),
    config: Path = typer.Option(Path("config/config.yaml")),
    model_dir: Path = typer.Option(Path("models")),
):
    """期待値ベースの買い目推奨."""
    cfg, svc = _load(config)
    svc.load(model_dir)
    pred = svc.predict_race(race_id)
    odds = _build_base_odds_from_csv(race_id, cfg)
    rec = svc.recommend_bets(race_id, budget=budget, odds=odds, prediction=pred)

    rprint(f"[bold]推奨買い目 race={race_id} 予算={budget}円[/bold]")
    table = Table()
    table.add_column("券種")
    table.add_column("選択", justify="left")
    table.add_column("オッズ", justify="right")
    table.add_column("確率", justify="right")
    table.add_column("EV", justify="right")
    table.add_column("ケリー", justify="right")
    table.add_column("推奨額", justify="right")
    for p in rec.picks:
        table.add_row(
            p.ticket.value, p.selection, f"{p.odds:5.1f}",
            f"{p.probability*100:5.1f}%", f"{p.expected_value*100:+5.1f}%",
            f"{p.kelly_fraction*100:4.1f}%", f"{p.stake:,}円",
        )
    console.print(table)
    rprint(f"合計: {rec.total_stake:,}円 / 期待利益: {rec.expected_profit:+.1f}円")


@app.command("bootstrap-data")
def bootstrap_data(
    out: Path = typer.Option(Path("sample_data")),
    n_races: int = typer.Option(1500),
    seed: int = typer.Option(42),
):
    """サンプル（合成）データを生成."""
    import subprocess
    import sys
    subprocess.check_call([
        sys.executable, "scripts/bootstrap_sample_data.py",
        "--out", str(out), "--n-races", str(n_races), "--seed", str(seed),
    ])


@app.command()
def live(
    race_id: str = typer.Argument(...),
    interval: float = typer.Option(10.0, help="ポーリング間隔 (秒)"),
    ticks: int = typer.Option(10, help="最大ティック数。0で無限"),
    mock: bool = typer.Option(True, help="Mockバックエンドを使用"),
    config: Path = typer.Option(Path("config/config.yaml")),
):
    """オッズポーリング（Mock）を起動して標準出力に配信."""
    cfg = load_config(config)
    base = _build_base_odds_from_csv(race_id, cfg)
    backend = MockOddsBackend(base, volatility=0.04, seed=42)
    stream = OddsStream()

    async def runner():
        task = asyncio.create_task(
            poll_odds(
                race_id, backend, stream,
                interval_sec=interval,
                max_ticks=None if ticks <= 0 else ticks,
                live_cfg=cfg.live,
            )
        )
        # 購読して stdout 出力
        q = await stream.subscribe(race_id)
        n = 0
        while True:
            try:
                payload = await asyncio.wait_for(q.get(), timeout=interval * 3)
            except asyncio.TimeoutError:
                break
            win_preview = {k: payload["odds"]["win"].get(k) for k in list(payload["odds"]["win"])[:5]}
            print(f"[tick {n}] ts={payload['ts']} win(1..5)={win_preview}")
            n += 1
            if ticks > 0 and n >= ticks:
                break
        await task

    asyncio.run(runner())


@app.command("json-predict")
def json_predict(
    race_id: str,
    config: Path = typer.Option(Path("config/config.yaml")),
    model_dir: Path = typer.Option(Path("models")),
):
    """JSON 形式で予測結果を出力（自動化用）."""
    _, svc = _load(config)
    svc.load(model_dir)
    pred = svc.predict_race(race_id)
    print(json.dumps(pred.model_dump(mode="json"), ensure_ascii=False, default=str))


if __name__ == "__main__":
    app()
