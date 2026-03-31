'use client';

import { useEffect, useState } from 'react';
import * as voiceService from '@/features/voice/services/voice.service';
import type { Session } from '@/features/voice/types';

interface UseSessionDetailResult {
  session: Session | null;
  loading: boolean;
  error: string | null;
}

const INITIAL_DELAY_MS = 1000;
const MAX_RETRIES = 5;

export function useSessionDetail(sessionId: string): UseSessionDetailResult {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId) return;

    let cancelled = false;
    let retryCount = 0;
    let timeoutId: ReturnType<typeof setTimeout>;

    async function fetchWithRetry() {
      if (cancelled) return;

      try {
        const data = await voiceService.getSession(sessionId);
        if (!cancelled) {
          setSession(data);
          setLoading(false);
        }
      } catch (err) {
        if (cancelled) return;

        retryCount++;

        if (retryCount >= MAX_RETRIES) {
          setError(err instanceof Error ? err.message : 'Failed to load session');
          setLoading(false);
          return;
        }

        // Exponential backoff: 1s, 2s, 4s, 8s, 16s
        const delayMs = INITIAL_DELAY_MS * Math.pow(2, retryCount - 1);
        console.log(
          `[useSessionDetail] Retry ${retryCount}/${MAX_RETRIES} after ${delayMs}ms for session ${sessionId}`
        );

        timeoutId = setTimeout(fetchWithRetry, delayMs);
      }
    }

    fetchWithRetry();

    return () => {
      cancelled = true;
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [sessionId]);

  return { session, loading, error };
}
