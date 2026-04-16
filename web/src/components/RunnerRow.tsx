'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { RunnerPrediction } from '@/lib/api';
import { pct, styleColor, styleLabel } from '@/lib/format';
import { cn } from '@/lib/cn';
import { ProbabilityBar } from './ProbabilityBar';
import { ChevronDown } from 'lucide-react';

interface Props {
  runner: RunnerPrediction;
  rank: number;
}

export function RunnerRow({ runner, rank }: Props) {
  const [open, setOpen] = useState(false);
  const accent =
    rank === 1 ? 'text-fuchsia-400' : rank === 2 ? 'text-sky-400' : rank === 3 ? 'text-emerald-400' : 'text-muted-fg';
  return (
    <div className="rounded-xl bg-card border border-border overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full p-3 flex items-center gap-3 text-left active:bg-muted/40"
      >
        <div className={cn('w-9 h-9 rounded-lg grid place-items-center font-bold tabular bg-muted/60', accent)}>
          {runner.horse_no}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold truncate">{runner.horse_name || `馬${runner.horse_no}`}</span>
            <span
              className={cn(
                'px-1.5 py-0.5 rounded-md text-[10px] font-medium border shrink-0',
                styleColor(runner.running_style)
              )}
            >
              {styleLabel(runner.running_style)}
            </span>
          </div>
          <div className="flex items-center gap-3 mt-1.5 text-[11px] text-muted-fg tabular">
            <span>テン {runner.ten_index.toFixed(0)}</span>
            <span>上がり {runner.agari_index.toFixed(0)}</span>
          </div>
          <div className="flex items-center gap-2 mt-1.5">
            <ProbabilityBar p1={runner.p_win} p2={runner.p_2nd} p3={runner.p_3rd} className="flex-1" />
            <span className="text-[11px] font-semibold tabular w-12 text-right">{pct(runner.p_place, 0)}</span>
          </div>
          <div className="flex items-center gap-2 mt-1 text-[10px] text-muted-fg tabular">
            <span className="text-fuchsia-400">1着 {pct(runner.p_win, 0)}</span>
            <span className="text-sky-400">2着 {pct(runner.p_2nd, 0)}</span>
            <span className="text-emerald-400">3着 {pct(runner.p_3rd, 0)}</span>
          </div>
        </div>
        <ChevronDown
          size={16}
          className={cn('text-muted-fg shrink-0 transition-transform', open && 'rotate-180')}
        />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden border-t border-border bg-muted/30"
          >
            <div className="p-3">
              <div className="text-[11px] text-muted-fg mb-2">要因（寄与大の順）</div>
              <div className="space-y-1.5">
                {runner.top_factors.map(([name, v], i) => (
                  <div key={i} className="flex items-center gap-2 text-[11px]">
                    <span className="w-20 shrink-0">{name}</span>
                    <div className="flex-1 h-1.5 bg-border rounded-full overflow-hidden">
                      <div
                        className={v >= 0 ? 'h-full bg-emerald-500' : 'h-full bg-rose-500'}
                        style={{ width: `${Math.min(Math.abs(v) * 50, 100)}%` }}
                      />
                    </div>
                    <span className={cn('w-10 text-right tabular', v >= 0 ? 'text-emerald-400' : 'text-rose-400')}>
                      {v >= 0 ? '+' : ''}
                      {v.toFixed(2)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
