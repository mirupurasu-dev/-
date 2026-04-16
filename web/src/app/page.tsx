import { RaceCard } from '@/components/RaceCard';
import { fetchJSON, RaceSummary } from '@/lib/api';

export const dynamic = 'force-dynamic';

async function getRaces(): Promise<RaceSummary[]> {
  try {
    const data = await fetchJSON<{ races: RaceSummary[] }>('/races/today');
    return data.races;
  } catch {
    return [];
  }
}

export default async function HomePage() {
  const races = await getRaces();
  return (
    <div className="px-4 pt-6 safe-top">
      <header className="mb-5">
        <div className="text-[11px] text-muted-fg">Today</div>
        <h1 className="text-2xl font-bold tracking-tight">レース</h1>
      </header>

      <section className="grid grid-cols-3 gap-2 mb-5">
        <Stat label="直近30日 回収率" value="—" accent="text-accent" />
        <Stat label="的中率" value="—" />
        <Stat label="期待値総和" value="—" />
      </section>

      <section className="space-y-2">
        {races.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border p-8 text-center text-sm text-muted-fg">
            本日のレースはありません
            <div className="mt-2 text-[11px]">
              バックエンドが起動しているか確認してください
            </div>
          </div>
        ) : (
          races.map((r) => <RaceCard key={r.race_id} race={r} />)
        )}
      </section>
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="rounded-2xl bg-card border border-border p-3">
      <div className="text-[10px] text-muted-fg">{label}</div>
      <div className={`text-lg font-bold tabular mt-0.5 ${accent ?? ''}`}>{value}</div>
    </div>
  );
}
