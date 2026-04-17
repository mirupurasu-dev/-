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
from ..backtest.signals import analyze_signals_from_source
from ..backtest.walkforward import walk_forward_backtest
from ..betting.odds_poller import MockOddsBackend, poll_odds
from ..betting.odds_stream import OddsStream
from ..config import load_config
from ..data.csv_source import CsvDataSource
from ..service import PredictionService

app = typer.Typer(add_completion=False, help="競馬予想AI CLI")
analyze_app = typer.Typer(help="シグナル分析・バックテスト")
app.add_typer(analyze_app, name="analyze")
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


@analyze_app.command("signals")
def analyze_signals(
    config: Path = typer.Option(Path("config/config.yaml")),
    top: int = typer.Option(15, help="上位N件を表示"),
    json_out: bool = typer.Option(False, "--json", help="JSONで出力"),
):
    """過去データから各シグナルの予測力 (IC, ICIR, t統計, NDCG@3) を算出."""
    cfg = load_config(config)
    src = CsvDataSource(cfg.data.csv_dir)
    rprint("[bold]シグナル分析開始…[/bold]")
    stats_list = analyze_signals_from_source(src)
    if json_out:
        print(json.dumps([s.to_dict() for s in stats_list], ensure_ascii=False, indent=2))
        return
    rprint(f"[green]分析完了[/green]: {len(stats_list)} signals across races")
    table = Table(title="シグナル優位性 (|IC| 降順)")
    table.add_column("#", justify="right")
    table.add_column("シグナル")
    table.add_column("平均IC", justify="right")
    table.add_column("ICIR", justify="right")
    table.add_column("t統計", justify="right")
    table.add_column("p値", justify="right")
    table.add_column("NDCG@3", justify="right")
    table.add_column("Win-LL", justify="right")
    table.add_column("推奨重み", justify="right")
    for i, s in enumerate(stats_list[:top], start=1):
        sig = "[green]" if s.mean_ic > 0 else "[red]"
        end = "[/]"
        table.add_row(
            str(i), s.name,
            f"{sig}{s.mean_ic:+.4f}{end}",
            f"{s.icir:+.2f}",
            f"{s.t_stat:+.2f}",
            f"{s.p_value:.3f}",
            f"{s.ndcg3:.3f}",
            f"{s.win_logloss:.3f}",
            f"{s.weight:+.3f}",
        )
    console.print(table)


@analyze_app.command("backtest")
def analyze_backtest(
    config: Path = typer.Option(Path("config/config.yaml")),
    n_folds: int = typer.Option(3, help="分割数"),
    min_train_races: int = typer.Option(300, help="最低学習レース数"),
    budget: int = typer.Option(10000, help="1レースあたり予算(円)"),
    tickets: str = typer.Option("win,place", help="使用券種（カンマ区切り）"),
    json_out: bool = typer.Option(False, "--json"),
):
    """Walk-forward で学習→買い目→払戻しをシミュレーション. 回収率・的中率を算出."""
    cfg = load_config(config)
    src = CsvDataSource(cfg.data.csv_dir)
    allowed = [t.strip() for t in tickets.split(",") if t.strip()]
    rprint(f"[bold]Walk-forward バックテスト開始…[/bold] folds={n_folds} tickets={allowed}")
    folds, result = walk_forward_backtest(
        src, cfg, n_folds=n_folds, min_train_races=min_train_races,
        allowed_tickets=allowed, budget=budget,
    )
    if json_out:
        print(json.dumps({
            "folds": [{"train_end": f.train_end.isoformat(), "n_train": f.n_train_races,
                        "test_start": f.test_start.isoformat(), "test_end": f.test_end.isoformat(),
                        "n_test": f.n_test_races} for f in folds],
            "summary": {
                "total_stake": result.total_stake,
                "total_payout": result.total_payout,
                "roi": result.roi,
                "hit_rate": result.hit_rate,
                "hit_pick_rate": result.hit_pick_rate,
                "n_races": result.n_races,
                "n_picks": result.n_picks,
            },
            "by_ticket": result.by_ticket,
        }, ensure_ascii=False, indent=2, default=str))
        return

    rprint(f"[green]結果[/green]")
    rprint(f"  参加レース: {result.n_races}, 買い目数: {result.n_picks}")
    rprint(f"  合計ベット: {result.total_stake:,}円")
    rprint(f"  合計払戻:   {result.total_payout:,}円")
    rprint(f"  [bold]回収率: {result.roi*100:.1f}%[/bold]  P&L: {result.total_payout - result.total_stake:+,}円")
    rprint(f"  レース的中率: {result.hit_rate*100:.1f}%")
    rprint(f"  買い目的中率: {result.hit_pick_rate*100:.1f}%")
    rprint()
    table = Table(title="券種別")
    table.add_column("券種")
    table.add_column("買目数", justify="right")
    table.add_column("的中", justify="right")
    table.add_column("的中率", justify="right")
    table.add_column("ベット", justify="right")
    table.add_column("払戻", justify="right")
    table.add_column("回収率", justify="right")
    for t, v in result.by_ticket.items():
        roi_pct = v["roi"] * 100
        color = "[green]" if roi_pct >= 100 else "[yellow]" if roi_pct >= 80 else "[red]"
        table.add_row(
            t, str(v["picks"]), str(v["hits"]),
            f"{v['hit_rate']*100:.1f}%",
            f"{v['stake']:,}",
            f"{v['payout']:,}",
            f"{color}{roi_pct:.1f}%[/]",
        )
    console.print(table)


if __name__ == "__main__":
    app()
