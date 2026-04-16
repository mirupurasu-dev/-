'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { ArrowLeft, Radio, Timer } from 'lucide-react';
import { PaceScenarioChip } from '@/components/PaceScenarioChip';
import { RecommendList } from '@/components/RecommendList';
import { OddsTicker } from '@/components/OddsTicker';
import { useLiveFeed } from '@/hooks/useLiveFeed';
import { cn } from '@/lib/cn';

export default function LivePage({ params }: { params: { id: string } }) {
  const { tick, connected } = useLiveFeed(params.id);
  const [started, setStarted] = useState(false);

  // ポーラを起動
  useEffect(() => {
    if (started) return;
    const base = process.env.NEXT_PUBLIC_API_BASE || window.location.origin.replace(':3000', ':8000');
    fetch(`${base}/api/live/start/${params.id}?interval_sec=10`, { method: 'POST' })
      .then(() => setStarted(true))
      .catch(() => setStarted(true));
  }, [params.id, started]);

  const horseNos = useMemo(() => {
    const pred = tick?.prediction;
    if (!pred) return [];
    return [...pred.runners].sort((a, b) => a.horse_no - b.horse_no).map((r) => r.horse_no);
  }, [tick]);

  return (
    <div className="px-4 pt-6 pb-6 safe-top">
      <div className="flex items-center justify-between mb-4">
        <Link href={`/race/${params.id}`} className="inline-flex items-center gap-1 text-sm text-muted-fg">
          <ArrowLeft size={14} /> 戻る
        </Link>
        <div className={cn(
          'inline-flex items-center gap-1 text-[10px] font-medium px-2 py-1 rounded-full border',
          connected
            ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
            : 'bg-muted text-muted-fg border-border'
        )}>
          <Radio size={10} className={connected ? 'animate-pulse-soft' : ''} />
          {connected ? 'LIVE' : '接続中…'}
        </div>
      </div>

      <header className="mb-4">
        <div className="text-[11px] text-muted-fg">{params.id}</div>
        <div className="flex items-baseline gap-2 mt-1">
          <h1 className="text-2xl font-bold tracking-tight">ライブ</h1>
          <span className="text-[10px] text-muted-fg inline-flex items-center gap-1 tabular">
            <Timer size={10} />
            {tick?.ts ? new Date(tick.ts).toLocaleTimeString('ja-JP') : '--:--:--'}
          </span>
        </div>
        {tick?.prediction && (
          <div className="mt-2">
            <div className="text-[10px] text-muted-fg mb-1">想定ペース</div>
            <PaceScenarioChip pace={tick.prediction.pace_prob} />
          </div>
        )}
      </header>

      <section className="mb-5">
        <h2 className="text-sm font-semibold mb-2">単勝オッズ</h2>
        <OddsTicker win={tick?.odds?.win} horseNos={horseNos} />
      </section>

      <section className="mb-5">
        <h2 className="text-sm font-semibold mb-2">推奨買い目（リアルタイム）</h2>
        {tick?.recommendation ? (
          <RecommendList
            picks={tick.recommendation.picks}
            totalStake={tick.recommendation.total_stake}
            expectedProfit={tick.recommendation.expected_profit}
          />
        ) : (
          <div className="rounded-2xl border border-dashed border-border p-6 text-center text-xs text-muted-fg">
            オッズ受信待ち…
          </div>
        )}
      </section>
    </div>
  );
}
