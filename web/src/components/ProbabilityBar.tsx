import { cn } from '@/lib/cn';

interface Props {
  p1: number;
  p2: number;
  p3: number;
  className?: string;
}

export function ProbabilityBar({ p1, p2, p3, className }: Props) {
  const total = p1 + p2 + p3;
  // Normalize for visual display if sums exceed 100% in UI
  const max = Math.max(1, total, 0.6);
  const w1 = (p1 / max) * 100;
  const w2 = (p2 / max) * 100;
  const w3 = (p3 / max) * 100;
  return (
    <div className={cn('w-full h-2 rounded-full overflow-hidden bg-muted flex', className)}>
      <div className="h-full bg-fuchsia-500" style={{ width: `${w1}%` }} title={`P(1着)=${(p1 * 100).toFixed(1)}%`} />
      <div className="h-full bg-sky-500" style={{ width: `${w2}%` }} title={`P(2着)=${(p2 * 100).toFixed(1)}%`} />
      <div className="h-full bg-emerald-500" style={{ width: `${w3}%` }} title={`P(3着)=${(p3 * 100).toFixed(1)}%`} />
    </div>
  );
}
