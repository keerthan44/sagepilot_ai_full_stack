'use client';

import { useEffect, useState } from 'react';
import * as voiceService from '@/features/voice/services/voice.service';
import type { Session } from '@/features/voice/types';

interface UseSessionsResult {
  sessions: Session[];
  loading: boolean;
  error: string | null;
}

export function useSessions(): UseSessionsResult {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    voiceService
      .listSessions()
      .then((data) => {
        if (!cancelled) setSessions(data);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load sessions');
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return { sessions, loading, error };
}
