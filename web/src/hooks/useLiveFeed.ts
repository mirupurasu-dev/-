'use client';

import { useEffect, useRef, useState } from 'react';
import { RacePrediction, RaceRecommendation, wsUrl } from '@/lib/api';

export interface LiveTick {
  type: 'tick';
  race_id: string;
  ts: string;
  odds: {
    win?: Record<string, number>;
    place?: Record<string, [number, number]>;
    quinella?: Record<string, number>;
    exacta?: Record<string, number>;
    trio?: Record<string, number>;
    trifecta?: Record<string, number>;
  };
  prediction: RacePrediction | null;
  recommendation: RaceRecommendation | null;
}

export function useLiveFeed(raceId: string | null) {
  const [tick, setTick] = useState<LiveTick | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!raceId) return;
    let alive = true;

    const connect = () => {
      const url = wsUrl(raceId);
      if (!url) return;
      const ws = new WebSocket(url);
      wsRef.current = ws;
      ws.onopen = () => {
        if (alive) setConnected(true);
        setError(null);
      };
      ws.onclose = () => {
        if (alive) {
          setConnected(false);
          // 3秒後に再接続
          setTimeout(() => alive && connect(), 3000);
        }
      };
      ws.onerror = () => {
        if (alive) setError('接続エラー');
      };
      ws.onmessage = (e) => {
        if (!alive) return;
        try {
          const msg: LiveTick = JSON.parse(e.data);
          setTick(msg);
        } catch {
          // noop
        }
      };
    };
    connect();
    return () => {
      alive = false;
      wsRef.current?.close();
    };
  }, [raceId]);

  return { tick, connected, error };
}
