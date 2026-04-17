import { fetchJSON, SignalStat, BacktestResponse } from '@/lib/api';

export const dynamic = 'force-dynamic';

async function getSignals(): Promise<SignalStat[]> {
  try {
    const r = await fetchJSON<{ signals: SignalStat[] }>('/analyze/signals');
    return r.signals;
  } catch {
    return [];
  }
}

async function getBacktest(): Promise<BacktestResponse | null> {
  try {
    return await fetchJSON<BacktestResponse>('/analyze/backtest?n_folds=3&min_train_races=300&budget=10000&tickets=win,place');
  } catch {
    return null;
  }
}

const FEATURE_JA: Record<string, string> = {
  distance_m: '距離',
  n_runners: '頭数',
  age: '年齢',
  weight_kg: '馬体重',
  surface_code: '芝ダ',
  turn_code: '回り',
  track_cond_code: '馬場状態',
  draw: '枠順',
  p_nige: '逃げ率',
  p_senko: '先行率',
  p_sashi: '差し率',
  p_oikomi: '追込率',
  ten_index: 'テン指数',
  agari_index: '上がり指数',
  ability_index: '実力指数',
  dist_fit: '距離適性',
  surface_fit: '馬場適性',
  track_cond_fit: '馬場状態適性',
  course_place_rate: '同コース複勝率',
  days_since_last: '休養日数',
};

function icBar(val: number, maxAbs: number) {
  const pct = Math.min(Math.abs(val) / maxAbs, 1) * 100;
  const pos = val >= 0;
  return (
    <div className="relative h-2 rounded-full bg-muted overflow-hidden flex items-center">
      <div className="absolute inset-y-0 left-1/2 w-px bg-border" />
      <div
        className={pos ? 'absolute left-1/2 h-full bg-emerald-500' : 'absolute right-1/2 h-full bg-rose-500'}
        style={{ width: `${pct / 2}%` }}
      />
    </div>
  );
}

function Pill({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="rounded-xl bg-card border border-border p-3">
      <div className="text-[10px] text-muted-fg">{label}</div>
      <div className={`text-lg font-bold tabular mt-0.5 ${accent ?? ''}`}>{value}</div>
    </div>
  );
}

export default async function AnalyzePage() {
  const [signals, bt] = await Promise.all([getSignals(), getBacktest()]);
  const maxAbs = Math.max(0.1, ...signals.map((s) => Math.abs(s.mean_ic)));

  return (
    <div className="px-4 pt-6 pb-6 safe-top">
      <header className="mb-5">
        <div className="text-[11px] text-muted-fg">Analysis</div>
        <h1 className="text-2xl font-bold tracking-tight">シグナル分析</h1>
        <p className="text-xs text-muted-fg mt-2">
          過去レースから各シグナルの相関優位性 (IC) を算出。|IC| が大きいほど予測に効く。
        </p>
      </header>

      {bt && (
        <section className="mb-6">
          <h2 className="text-sm font-semibold mb-2">バックテスト</h2>
          <div className="grid grid-cols-3 gap-2 mb-2">
            <Pill
              label="回収率"
              value={`${(bt.summary.roi * 100).toFixed(1)}%`}
              accent={bt.summary.roi >= 1 ? 'text-emerald-400' : 'text-rose-400'}
            />
            <Pill label="レース的中率" value={`${(bt.summary.hit_rate * 100).toFixed(1)}%`} />
            <Pill label="買目的中率" value={`${(bt.summary.hit_pick_rate * 100).toFixed(1)}%`} />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <Pill label="参加レース" value={`${bt.summary.n_races.toLocaleString()}`} />
            <Pill
              label="P&L"
              value={`¥${(bt.summary.total_payout - bt.summary.total_stake).toLocaleString('ja-JP')}`}
              accent={bt.summary.total_payout >= bt.summary.total_stake ? 'text-emerald-400' : 'text-rose-400'}
            />
          </div>
          <div className="mt-3 space-y-1.5">
            {Object.entries(bt.by_ticket).map(([t, v]) => (
              <div key={t} className="flex items-center gap-2 text-[11px]">
                <span className="w-14 shrink-0">{t}</span>
                <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                  <div
                    className={v.roi >= 1 ? 'h-full bg-emerald-500' : 'h-full bg-rose-500'}
                    style={{ width: `${Math.min(v.roi * 50, 100)}%` }}
                  />
                </div>
                <span className="tabular w-14 text-right">{(v.roi * 100).toFixed(0)}%</span>
                <span className="tabular w-12 text-right text-muted-fg">{(v.hit_rate * 100).toFixed(0)}%</span>
              </div>
            ))}
          </div>
        </section>
      )}

      <section>
        <h2 className="text-sm font-semibold mb-2 flex items-center justify-between">
          シグナル優位性
          <span className="text-[10px] font-normal text-muted-fg">|IC| 降順</span>
        </h2>
        {signals.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border p-6 text-center text-sm text-muted-fg">
            データなし
          </div>
        ) : (
          <div className="space-y-2">
            {signals.map((s, i) => (
              <div key={s.name} className="rounded-xl bg-card border border-border p-3">
                <div className="flex items-center gap-2">
                  <span className="w-5 text-[11px] text-muted-fg tabular">{i + 1}</span>
                  <span className="text-sm font-semibold flex-1 truncate">
                    {FEATURE_JA[s.name] ?? s.name}
                  </span>
                  <span
                    className={`text-xs font-semibold tabular ${
                      s.mean_ic >= 0 ? 'text-emerald-400' : 'text-rose-400'
                    }`}
                  >
                    IC {s.mean_ic >= 0 ? '+' : ''}
                    {s.mean_ic.toFixed(3)}
                  </span>
                </div>
                <div className="mt-2">{icBar(s.mean_ic, maxAbs)}</div>
                <div className="flex items-center gap-3 mt-2 text-[10px] text-muted-fg tabular">
                  <span>ICIR {s.icir >= 0 ? '+' : ''}{s.icir.toFixed(2)}</span>
                  <span>t={s.t_stat >= 0 ? '+' : ''}{s.t_stat.toFixed(1)}</span>
                  <span>p={s.p_value.toExponential(1)}</span>
                  <span>NDCG@3={s.ndcg3.toFixed(3)}</span>
                  <span className="ml-auto">w={s.weight >= 0 ? '+' : ''}{s.weight.toFixed(3)}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
