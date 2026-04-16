import Link from 'next/link';
import { ArrowLeft, Radio } from 'lucide-react';
import { PaceScenarioChip } from '@/components/PaceScenarioChip';
import { RunnerRow } from '@/components/RunnerRow';
import { RecommendList } from '@/components/RecommendList';
import { fetchJSON, RecommendResponse } from '@/lib/api';

export const dynamic = 'force-dynamic';

async function getData(raceId: string): Promise<RecommendResponse | null> {
  try {
    return await fetchJSON<RecommendResponse>(`/recommend/${raceId}?budget=10000`);
  } catch {
    return null;
  }
}

export default async function RacePage({ params }: { params: { id: string } }) {
  const data = await getData(params.id);

  if (!data) {
    return (
      <div className="p-4 text-center text-muted-fg">
        <Link href="/" className="inline-flex items-center gap-1 text-sm mb-4">
          <ArrowLeft size={14} /> 戻る
        </Link>
        <p>予測データを取得できませんでした。</p>
        <p className="text-xs mt-2">モデル学習と API 起動を確認してください。</p>
      </div>
    );
  }

  const { prediction, recommendation } = data;

  return (
    <div className="px-4 pt-6 pb-6 safe-top">
      <div className="flex items-center justify-between mb-4">
        <Link href="/" className="inline-flex items-center gap-1 text-sm text-muted-fg">
          <ArrowLeft size={14} /> 戻る
        </Link>
        <Link
          href={`/race/${params.id}/live`}
          className="inline-flex items-center gap-1 text-xs font-medium px-3 py-1.5 rounded-full bg-accent text-accent-fg"
        >
          <Radio size={12} /> ライブ
        </Link>
      </div>

      <header className="mb-4">
        <div className="text-[11px] text-muted-fg">{prediction.race_id}</div>
        <h1 className="text-2xl font-bold tracking-tight">予測</h1>
        <div className="mt-2">
          <div className="text-[10px] text-muted-fg mb-1">想定ペース</div>
          <PaceScenarioChip pace={prediction.pace_prob} />
        </div>
      </header>

      <section className="mb-6">
        <h2 className="text-sm font-semibold mb-2 flex items-center justify-between">
          推奨買い目
          <span className="text-[10px] font-normal text-muted-fg">予算 ¥10,000</span>
        </h2>
        <RecommendList
          picks={recommendation.picks}
          totalStake={recommendation.total_stake}
          expectedProfit={recommendation.expected_profit}
        />
      </section>

      <section>
        <h2 className="text-sm font-semibold mb-2">出走馬（P(複勝)順）</h2>
        <div className="space-y-2">
          {prediction.runners.map((r, i) => (
            <RunnerRow key={r.horse_no} runner={r} rank={i + 1} />
          ))}
        </div>
      </section>
    </div>
  );
}
