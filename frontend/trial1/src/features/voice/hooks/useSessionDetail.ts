'use client';

import { useEffect, useState } from 'react';
import * as voiceService from '@/features/voice/services/voice.service';
import type { Session } from '@/features/voice/types';

interface UseSessionDetailResult {
  session: Session | null;
  loading: boolean;
  error: string | null;
}

export function useSessionDetail(sessionId: string): UseSessionDetailResult {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId) return;

    let cancelled = false;

    voiceService
      .getSession(sessionId)
      .then((data) => {
        if (!cancelled) setSession(data);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load session');
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  return { session, loading, error };
}
