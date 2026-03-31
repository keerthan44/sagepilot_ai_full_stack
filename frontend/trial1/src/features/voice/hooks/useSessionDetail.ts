'use client';

import { useEffect, useState } from 'react';
import * as voiceService from '@/features/voice/services/voice.service';
import type { Session } from '@/features/voice/types';

interface UseSessionDetailResult {
  session: Session | null;
  /** True until the first successful GET /sessions/:id */
  loading: boolean;
  /** True while transcript is still empty/null and we are polling for updates */
  transcriptLoading: boolean;
  error: string | null;
}

const INITIAL_DELAY_MS = 1000;
const MAX_FETCH_FAILURES = 5;
/** Poll attempts after session exists but transcript is still empty */
const MAX_TRANSCRIPT_POLLS = 5;

function hasTranscript(data: Session): boolean {
  const t = data.transcript;
  return Array.isArray(t) && t.length > 0;
}

export function useSessionDetail(sessionId: string): UseSessionDetailResult {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [transcriptLoading, setTranscriptLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId) return;

    let cancelled = false;
    let timeoutId: ReturnType<typeof setTimeout> | undefined;

    let fetchFailureCount = 0;
    let transcriptPollCount = 0;
    let hasLoadedSessionOnce = false;

    function schedule(fn: () => void, delayMs: number) {
      timeoutId = setTimeout(() => {
        void fn();
      }, delayMs);
    }

    async function loadSession() {
      if (cancelled) return;

      try {
        const data = await voiceService.getSession(sessionId);
        if (cancelled) return;

        fetchFailureCount = 0;
        hasLoadedSessionOnce = true;
        setSession(data);
        setLoading(false);
        setError(null);

        if (hasTranscript(data)) {
          setTranscriptLoading(false);
          transcriptPollCount = 0;
          return;
        }

        transcriptPollCount += 1;
        if (transcriptPollCount > MAX_TRANSCRIPT_POLLS) {
          setTranscriptLoading(false);
          return;
        }

        setTranscriptLoading(true);
        const delayMs = INITIAL_DELAY_MS * Math.pow(2, transcriptPollCount - 1);
        schedule(loadSession, delayMs);
      } catch (err) {
        if (cancelled) return;

        if (!hasLoadedSessionOnce) {
          fetchFailureCount += 1;
          if (fetchFailureCount >= MAX_FETCH_FAILURES) {
            setError(err instanceof Error ? err.message : 'Failed to load session');
            setLoading(false);
            setTranscriptLoading(false);
            return;
          }
          const delayMs = INITIAL_DELAY_MS * Math.pow(2, fetchFailureCount - 1);
          schedule(loadSession, delayMs);
          return;
        }

        // Session was already shown; polling failed — retry with same transcript budget
        transcriptPollCount += 1;
        if (transcriptPollCount > MAX_TRANSCRIPT_POLLS) {
          setTranscriptLoading(false);
          return;
        }
        const delayMs = INITIAL_DELAY_MS * Math.pow(2, transcriptPollCount - 1);
        schedule(loadSession, delayMs);
      }
    }

    void loadSession();

    return () => {
      cancelled = true;
      if (timeoutId !== undefined) clearTimeout(timeoutId);
    };
  }, [sessionId]);

  return { session, loading, error, transcriptLoading };
}
