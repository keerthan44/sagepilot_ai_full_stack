import type { Session, StartSessionPayload, StartSessionResponse } from '@/features/voice/types';
import { apiFetch } from '@/lib/fetch';

export function startSession(payload: StartSessionPayload): Promise<StartSessionResponse> {
  return apiFetch<StartSessionResponse>('/sessions/start', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function listSessions(): Promise<Session[]> {
  return apiFetch<Session[]>('/sessions/');
}

export function getSession(sessionId: string): Promise<Session> {
  return apiFetch<Session>(`/sessions/${sessionId}`);
}
