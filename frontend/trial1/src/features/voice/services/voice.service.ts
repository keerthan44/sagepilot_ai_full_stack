import * as voiceApi from '@/features/voice/api/voice.api';
import type { Session, StartSessionPayload, StartSessionResponse } from '@/features/voice/types';

export async function startSession(payload: StartSessionPayload): Promise<StartSessionResponse> {
  return voiceApi.startSession(payload);
}

export async function listSessions(): Promise<Session[]> {
  return voiceApi.listSessions();
}

export async function getSession(sessionId: string): Promise<Session> {
  return voiceApi.getSession(sessionId);
}
