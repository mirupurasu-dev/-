import Link from 'next/link';
import { RaceSummary } from '@/lib/api';
import { courseAccent, timeUntil } from '@/lib/format';
import { cn } from '@/lib/cn';
import { ChevronRight, Clock } from 'lucide-react';

interface Props {
  race: RaceSummary;
}

export function RaceCard({ race }: Props) {
  const accent = courseAccent(race.course);
  return (
    <Link
      href={`/race/${race.race_id}`}
      className="block relative rounded-2xl bg-card border border-border overflow-hidden active:scale-[0.99] transition-transform"
    >
      <div className={cn('absolute inset-y-0 left-0 w-1 bg-gradient-to-b', accent)} />
      <div className="p-4 pl-5 flex items-center gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-medium text-muted-fg">
              {race.course} · {race.race_no}R
            </span>
            <span className="text-[10px] text-muted-fg">
              {race.surface === 'turf' ? '芝' : 'ダート'} {race.distance_m}m
            </span>
          </div>
          <div className="text-base font-semibold truncate mt-0.5">
            {race.race_name || `第${race.race_no}レース`}
          </div>
          <div className="flex items-center gap-1.5 mt-1.5 text-xs text-muted-fg tabular">
            <Clock size={12} strokeWidth={2} />
            <span>{timeUntil(race.post_time)}</span>
            <span className="text-border">·</span>
            <span>{race.n_runners}頭</span>
          </div>
        </div>
        <ChevronRight className="text-muted-fg shrink-0" size={18} />
      </div>
    </Link>
  );
}
