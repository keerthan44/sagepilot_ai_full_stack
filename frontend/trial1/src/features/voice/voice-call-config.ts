import type { AgentOption } from '@/features/voice/components/AgentSelector';

export const VOICE_CALL_AGENT_OPTIONS: AgentOption[] = [
  {
    value: 'general_assistant',
    label: 'General assistant',
    description:
      'You can talk about anything. Available tool calls: get_weather, get_current_time.',
  },
  {
    value: 'customer_support',
    label: 'Customer support',
    description:
      'You can talk about a specific order. Available tool calls: cancel_order, get_return_policy, lookup_order.',
  },
];

export const VOICE_CALL_TTS_OPTIONS = [
  { value: 'elevenlabs', label: 'ElevenLabs' },
  { value: 'cartesia', label: 'Cartesia' },
] as const;

export const VOICE_CALL_STT_OPTIONS = [
  { value: 'deepgram', label: 'Deepgram' },
  { value: 'assemblyai', label: 'AssemblyAI' },
] as const;

export const VOICE_CALL_LLM_OPTIONS = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'gemini', label: 'Gemini' },
] as const;

export interface VoiceCallDisplayFromUrl {
  agentValue: string;
  agentLabel: string;
  agentDescription: string;
  ttsLabel: string;
  sttLabel: string;
  llmLabel: string;
}

function labelFromOptions(
  options: readonly { value: string; label: string }[],
  value: string
): string {
  if (!value) return 'Not specified';
  return options.find((o) => o.value === value)?.label ?? value;
}

/** Read STT/TTS/LLM provider slugs from session `config` (API may use snake_case or camelCase). */
export function sessionVoiceProviderLabels(config: Record<string, unknown> | null | undefined): {
  stt: string;
  tts: string;
  llm: string;
} {
  const c = config ?? {};
  const stt =
    typeof c.stt_provider === 'string'
      ? c.stt_provider
      : typeof c.sttProvider === 'string'
        ? c.sttProvider
        : '';
  const tts =
    typeof c.tts_provider === 'string'
      ? c.tts_provider
      : typeof c.ttsProvider === 'string'
        ? c.ttsProvider
        : '';
  const llm =
    typeof c.llm_provider === 'string'
      ? c.llm_provider
      : typeof c.llmProvider === 'string'
        ? c.llmProvider
        : '';
  return {
    stt: labelFromOptions(VOICE_CALL_STT_OPTIONS, stt),
    tts: labelFromOptions(VOICE_CALL_TTS_OPTIONS, tts),
    llm: labelFromOptions(VOICE_CALL_LLM_OPTIONS, llm),
  };
}

function pickConfigRecord(value: unknown): Record<string, unknown> | null {
  if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return null;
}

/** STT/TTS/LLM option payloads from session `config` (snake_case or camelCase). */
export function sessionVoiceSttTtsConfigs(config: Record<string, unknown> | null | undefined): {
  sttConfig: Record<string, unknown> | null;
  ttsConfig: Record<string, unknown> | null;
  llmConfig: Record<string, unknown> | null;
} {
  const c = config ?? {};
  return {
    sttConfig: pickConfigRecord(c.stt_config ?? c.sttConfig),
    ttsConfig: pickConfigRecord(c.tts_config ?? c.ttsConfig),
    llmConfig: pickConfigRecord(c.llm_config ?? c.llmConfig),
  };
}

export function voiceCallDisplayFromSearchParams(
  searchParams: URLSearchParams
): VoiceCallDisplayFromUrl {
  const agentValue = searchParams.get('agent_name') ?? 'general_assistant';
  const agent = VOICE_CALL_AGENT_OPTIONS.find((a) => a.value === agentValue);

  return {
    agentValue,
    agentLabel: agent?.label ?? humanizeAgentName(agentValue),
    agentDescription:
      agent?.description ??
      'Agent details were not passed in the URL. Start a new call from the home page for full context.',
    ttsLabel: labelFromOptions(VOICE_CALL_TTS_OPTIONS, searchParams.get('tts_provider') ?? ''),
    sttLabel: labelFromOptions(VOICE_CALL_STT_OPTIONS, searchParams.get('stt_provider') ?? ''),
    llmLabel: labelFromOptions(VOICE_CALL_LLM_OPTIONS, searchParams.get('llm_provider') ?? ''),
  };
}

function humanizeAgentName(text: string): string {
  if (!text) return '';
  return text
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/[_-]+/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .trim();
}
