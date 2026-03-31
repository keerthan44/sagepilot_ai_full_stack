export interface StartSessionPayload {
  llm_provider: string;
  llm_config?: Record<string, unknown> | null;
  stt_provider: string;
  stt_config?: Record<string, unknown> | null;
  tts_provider: string;
  tts_config?: Record<string, unknown> | null;
  agent_name: string;
}

export interface StartSessionResponse {
  session_id: string;
  token: string;
  room_name: string;
}

export interface ToolCall {
  name: string;
  args: Record<string, unknown>;
  id: string;
}

export interface TranscriptEntry {
  role: string;
  content: string;
  timestamp: number;
  tool_calls?: ToolCall[];
  tool_call_id?: string;
  metadata?: {
    name?: string;
    [key: string]: unknown;
  };
}

export interface Session {
  id: string;
  agent_name: string;
  config: Record<string, unknown>;
  transcript: TranscriptEntry[] | null;
  created_at: string;
}

export type VoiceConnectionState = 'idle' | 'connecting' | 'listening' | 'speaking';
