// フロントから API を叩くためのクライアント

export const API_BASE =
  typeof window === 'undefined'
    ? process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000'
    : '';

// クライアントサイド時は Next.js rewrite 経由、SSR時は直接 API_BASE へ
function url(path: string) {
  if (typeof window === 'undefined') return `${API_BASE}/api${path}`;
  return `/api-proxy${path}`;
}

export async function fetchJSON<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url(path), { cache: 'no-store', ...init });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

// WebSocket URL: クライアント側からのみ呼ばれる
export function wsUrl(raceId: string) {
  if (typeof window === 'undefined') return '';
  const apiBase = process.env.NEXT_PUBLIC_API_BASE || window.location.origin.replace(':3000', ':8000');
  const u = new URL(apiBase);
  u.protocol = u.protocol === 'https:' ? 'wss:' : 'ws:';
  u.pathname = `/ws/live/${raceId}`;
  return u.toString();
}

// 型
export interface RaceSummary {
  race_id: string;
  course: string;
  race_no: number;
  race_name: string;
  distance_m: number;
  surface: string;
  track_condition: string;
  n_runners: number;
  post_time: string;
}

export interface RunnerPrediction {
  race_id: string;
  horse_no: number;
  horse_name: string;
  score: number;
  p_win: number;
  p_2nd: number;
  p_3rd: number;
  p_place: number;
  ten_index: number;
  agari_index: number;
  running_style: 'nige' | 'senko' | 'sashi' | 'oikomi';
  top_factors: [string, number][];
}

export interface RacePrediction {
  race_id: string;
  pace_prob: { high: number; mid: number; slow: number };
  runners: RunnerPrediction[];
  computed_at: string;
}

export interface BetPick {
  ticket: string;
  selection: string;
  odds: number;
  probability: number;
  expected_value: number;
  kelly_fraction: number;
  stake: number;
}

export interface RaceRecommendation {
  race_id: string;
  budget: number;
  picks: BetPick[];
  total_stake: number;
  expected_profit: number;
  computed_at: string;
}

export interface RecommendResponse {
  prediction: RacePrediction;
  recommendation: RaceRecommendation;
  odds_ts: string | null;
}

export interface SignalStat {
  name: string;
  n_races: number;
  mean_ic: number;
  std_ic: number;
  icir: number;
  t_stat: number;
  p_value: number;
  ndcg3: number;
  win_logloss: number;
  weight: number;
}

export interface BacktestSummary {
  total_stake: number;
  total_payout: number;
  roi: number;
  hit_rate: number;
  hit_pick_rate: number;
  n_races: number;
  n_picks: number;
}

export interface BacktestResponse {
  folds: Array<{ train_end: string; test_start: string; test_end: string; n_train_races: number; n_test_races: number }>;
  summary: BacktestSummary;
  by_ticket: Record<string, { picks: number; hits: number; hit_rate: number; stake: number; payout: number; roi: number }>;
  per_race_pl_sample: Array<{ race_id: string; stake: number; payout: number; pl: number; hit: boolean }>;
}
