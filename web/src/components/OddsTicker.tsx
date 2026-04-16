'use client';

import { useEffect, useRef, useState } from 'react';
import { cn } from '@/lib/cn';
import { odds as fmtOdds } from '@/lib/format';
import { ArrowDown, ArrowUp } from 'lucide-react';

interface Props {
  win: Record<string, number> | undefined;
  horseNos: number[];
}

/** Win oddsを馬番ごとに表示。前値との差分で↑↓色変化 */
export function OddsTicker({ win, horseNos }: Props) {
  const prev = useRef<Record<number, number>>({});
  const [flash, setFlash] = useState<Record<number, 'up' | 'down' | null>>({});

  useEffect(() => {
    if (!win) return;
    const updates: Record<number, 'up' | 'down' | null> = {};
    for (const no of horseNos) {
      const cur = win[String(no)] ?? win[no as unknown as string];
      const old = prev.current[no];
      if (old !== undefined && cur !== undefined) {
        if (cur > old + 0.1) updates[no] = 'up';
        else if (cur < old - 0.1) updates[no] = 'down';
      }
      if (cur !== undefined) prev.current[no] = cur;
    }
    setFlash(updates);
    const t = setTimeout(() => setFlash({}), 1500);
    return () => clearTimeout(t);
  }, [win, horseNos]);

  if (!win) return null;

  return (
    <div className="grid grid-cols-4 gap-1.5">
      {horseNos.map((no) => {
        const v = win[String(no)];
        if (v === undefined) return null;
        const state = flash[no];
        return (
          <div
            key={no}
            className={cn(
              'rounded-lg border border-border bg-card px-2 py-1.5 flex items-center justify-between',
              state === 'up' && 'animate-flash-up',
              state === 'down' && 'animate-flash-down'
            )}
          >
            <span className="text-[10px] text-muted-fg w-4 tabular">{no}</span>
            <span className="text-sm font-semibold tabular">{fmtOdds(v)}</span>
            {state === 'up' && <ArrowUp size={10} className="text-rose-400" />}
            {state === 'down' && <ArrowDown size={10} className="text-emerald-400" />}
          </div>
        );
      })}
    </div>
  );
}
