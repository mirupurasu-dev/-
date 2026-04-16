export function pct(v: number, digits = 1) {
  return `${(v * 100).toFixed(digits)}%`;
}

export function yen(v: number) {
  return `¥${v.toLocaleString('ja-JP')}`;
}

export function odds(v: number) {
  return v >= 100 ? v.toFixed(0) : v.toFixed(1);
}

export function ticketLabel(t: string) {
  return (
    {
      win: '単勝',
      place: '複勝',
      quinella: '馬連',
      exacta: '馬単',
      trio: '3連複',
      trifecta: '3連単',
    }[t] ?? t
  );
}

export function styleLabel(s: string) {
  return (
    {
      nige: '逃',
      senko: '先',
      sashi: '差',
      oikomi: '追',
    }[s] ?? s
  );
}

export function styleColor(s: string) {
  return (
    {
      nige: 'bg-rose-500/20 text-rose-400 border-rose-500/30',
      senko: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
      sashi: 'bg-sky-500/20 text-sky-400 border-sky-500/30',
      oikomi: 'bg-violet-500/20 text-violet-400 border-violet-500/30',
    }[s] ?? 'bg-muted text-muted-fg'
  );
}

export function evColor(ev: number) {
  if (ev < 0) return 'text-muted-fg';
  if (ev < 0.1) return 'text-amber-400';
  if (ev < 0.3) return 'text-emerald-400';
  return 'text-fuchsia-400';
}

export function courseAccent(course: string) {
  const map: Record<string, string> = {
    東京: 'from-sky-500 to-indigo-500',
    中山: 'from-emerald-500 to-teal-500',
    阪神: 'from-rose-500 to-red-500',
    京都: 'from-violet-500 to-purple-500',
    中京: 'from-amber-500 to-orange-500',
    新潟: 'from-cyan-500 to-sky-500',
    福島: 'from-teal-500 to-green-500',
    小倉: 'from-orange-500 to-amber-500',
    札幌: 'from-indigo-500 to-blue-500',
    函館: 'from-blue-500 to-cyan-500',
  };
  return map[course] ?? 'from-slate-500 to-zinc-500';
}

export function timeUntil(iso: string) {
  const t = new Date(iso).getTime() - Date.now();
  if (t <= 0) return '発走済み';
  const m = Math.floor(t / 60000);
  const s = Math.floor((t % 60000) / 1000);
  if (m >= 60) return `${Math.floor(m / 60)}時間${m % 60}分`;
  return `${m}分${s.toString().padStart(2, '0')}秒`;
}
