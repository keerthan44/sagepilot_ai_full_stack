'use client';

import { useCallback, useState } from 'react';
import * as voiceService from '@/features/voice/services/voice.service';
import type { StartSessionPayload, StartSessionResponse } from '@/features/voice/types';

interface UseStartSessionResult {
  startSession: (payload: StartSessionPayload) => Promise<StartSessionResponse | null>;
  loading: boolean;
  error: string | null;
}

export function useStartSession(): UseStartSessionResult {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const startSession = useCallback(async (payload: StartSessionPayload) => {
    setLoading(true);
    setError(null);
    try {
      const result = await voiceService.startSession(payload);
      return result;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to start session';
      setError(message);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  return { startSession, loading, error };
}
