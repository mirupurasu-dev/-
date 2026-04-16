'use client';

import { motion } from 'framer-motion';
import { BetPick } from '@/lib/api';
import { cn } from '@/lib/cn';
import { evColor, odds, pct, ticketLabel, yen } from '@/lib/format';

interface Props {
  picks: BetPick[];
  totalStake: number;
  expectedProfit: number;
}

export function RecommendList({ picks, totalStake, expectedProfit }: Props) {
  if (!picks.length) {
    return (
      <div className="rounded-2xl border border-dashed border-border p-6 text-center text-sm text-muted-fg">
        期待値プラスの買い目はありません
      </div>
    );
  }
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between text-[11px] text-muted-fg px-1">
        <span>合計 {yen(totalStake)}</span>
        <span className="tabular">
          期待利益 <span className="text-emerald-400">{yen(Math.round(expectedProfit))}</span>
        </span>
      </div>
      <div className="flex gap-3 overflow-x-auto no-scrollbar snap-x snap-mandatory -mx-4 px-4 pb-1">
        {picks.map((p, i) => (
          <motion.div
            key={`${p.ticket}-${p.selection}`}
            layout
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.04 }}
            className="snap-start shrink-0 w-[72%] max-w-[320px] rounded-2xl bg-card border border-border p-4"
          >
            <div className="flex items-center justify-between text-[11px] text-muted-fg">
              <span className="font-medium text-fg">{ticketLabel(p.ticket)}</span>
              <span className={cn('tabular font-semibold', evColor(p.expected_value))}>
                EV {p.expected_value >= 0 ? '+' : ''}
                {pct(p.expected_value, 0)}
              </span>
            </div>
            <div className="text-xl font-bold mt-2 tabular tracking-tight break-all">
              {p.selection}
            </div>
            <div className="grid grid-cols-3 gap-2 mt-3 text-[11px]">
              <div>
                <div className="text-muted-fg">オッズ</div>
                <div className="tabular font-semibold">{odds(p.odds)}</div>
              </div>
              <div>
                <div className="text-muted-fg">確率</div>
                <div className="tabular font-semibold">{pct(p.probability, 1)}</div>
              </div>
              <div>
                <div className="text-muted-fg">Kelly</div>
                <div className="tabular font-semibold">{pct(p.kelly_fraction, 1)}</div>
              </div>
            </div>
            <div className="mt-3 pt-3 border-t border-border flex items-center justify-between">
              <span className="text-[11px] text-muted-fg">推奨額</span>
              <span className="text-lg font-bold tabular text-accent">{yen(p.stake)}</span>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
