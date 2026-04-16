import { cn } from '@/lib/cn';
import { pct } from '@/lib/format';

interface Props {
  pace: { high: number; mid: number; slow: number };
  className?: string;
}

const labels = {
  high: { label: 'ハイ', color: 'bg-rose-500/20 text-rose-400 border-rose-500/30' },
  mid: { label: 'ミドル', color: 'bg-amber-500/20 text-amber-400 border-amber-500/30' },
  slow: { label: 'スロー', color: 'bg-sky-500/20 text-sky-400 border-sky-500/30' },
} as const;

export function PaceScenarioChip({ pace, className }: Props) {
  const entries = Object.entries(pace) as [keyof typeof labels, number][];
  return (
    <div className={cn('flex items-center gap-1.5 flex-wrap', className)}>
      {entries.map(([k, v]) => (
        <span
          key={k}
          className={cn(
            'px-2 py-0.5 rounded-full text-[10px] font-medium border tabular',
            labels[k].color
          )}
        >
          {labels[k].label} {pct(v, 0)}
        </span>
      ))}
    </div>
  );
}
