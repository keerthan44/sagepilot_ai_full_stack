export interface StartSessionPayload {
  voice: Record<string, unknown>;
  agent: Record<string, unknown>;
  llm: Record<string, unknown>;
}

export interface StartSessionResponse {
  session_id: string;
  token: string;
  room_name: string;
}

export interface TranscriptEntry {
  role: string;
  content: string;
  tool_call: Record<string, unknown>;
}

export interface Session {
  id: string;
  agent_name: string;
  config: Record<string, unknown>;
  transcript: TranscriptEntry[] | null;
  created_at: string;
}

export type VoiceConnectionState = 'idle' | 'connecting' | 'listening' | 'speaking';
