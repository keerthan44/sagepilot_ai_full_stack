'use client';

import { useState } from 'react';
import { type AgentOption, AgentSelector } from '@/features/voice/components/AgentSelector';
import { ProviderSelector } from '@/features/voice/components/ProviderSelector';
import { StartCallButton } from '@/features/voice/components/StartCallButton';

const AGENT_OPTIONS: AgentOption[] = [
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

const TTS_OPTIONS = [
  { value: 'elevenlabs', label: 'ElevenLabs' },
  { value: 'cartesia', label: 'Cartesia' },
];

const STT_OPTIONS = [
  { value: 'deepgram', label: 'Deepgram' },
  { value: 'assemblyai', label: 'AssemblyAI' },
];

const LLM_OPTIONS = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'gemini', label: 'Gemini' },
];

export default function HomePage() {
  const [agentName, setAgentName] = useState('general_assistant');
  const [ttsProvider, setTtsProvider] = useState('elevenlabs');
  const [sttProvider, setSttProvider] = useState('deepgram');
  const [llmProvider, setLlmProvider] = useState('openai');

  const payload = {
    agent_name: agentName,
    tts_provider: ttsProvider,
    stt_provider: sttProvider,
    llm_provider: llmProvider,
  };

  return (
    <div className="flex flex-col gap-10">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Start a Voice Call</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Configure your agent and providers, then start a call.
        </p>
      </div>

      <div className="border-border bg-card flex flex-col gap-8 rounded-xl border p-6 shadow-sm">
        <section className="flex flex-col gap-4">
          <h2 className="text-base font-semibold">Agent configuration</h2>
          <AgentSelector value={agentName} onChange={setAgentName} options={AGENT_OPTIONS} />
        </section>

        <div className="bg-border h-px" />

        <section className="flex flex-col gap-4">
          <h2 className="text-base font-semibold">Voice configuration</h2>
          <ProviderSelector
            label="TTS provider"
            name="tts_provider"
            value={ttsProvider}
            onChange={setTtsProvider}
            options={TTS_OPTIONS}
          />
          {ttsProvider === 'elevenlabs' ? (
            <p className="flex gap-2 rounded-md bg-amber-500/15 px-3 py-2 text-xs text-amber-900 dark:text-amber-200">
              <span aria-hidden>⚠️</span>
              <span>
                ElevenLabs free-tier API keys often do not work when requests come from cloud
                providers—ElevenLabs has restricted that. Use a paid plan or run from a private IP
                if you hit errors.
              </span>
            </p>
          ) : null}
          {/* {ttsProvider === 'cartesia' ? (
            <p className="flex gap-2 rounded-md bg-yellow-500/15 px-3 py-2 text-xs text-yellow-800 dark:text-yellow-200">
              <span aria-hidden>🐛</span>
              <span>
                Latency might be higher with Cartesia because the LiveKit turn detector is not
                working cleanly yet.
              </span>
            </p>
          ) : null} */}
          <ProviderSelector
            label="STT provider"
            name="stt_provider"
            value={sttProvider}
            onChange={setSttProvider}
            options={STT_OPTIONS}
          />
        </section>

        <div className="bg-border h-px" />

        <section className="flex flex-col gap-4">
          <h2 className="text-base font-semibold">LLM configuration</h2>
          <ProviderSelector
            label="LLM provider — fixed to OpenAI for now"
            name="llm_provider"
            value={llmProvider}
            onChange={setLlmProvider}
            options={LLM_OPTIONS}
            disabled={true}
          />
        </section>

        <div className="bg-border h-px" />

        <StartCallButton payload={payload} />
      </div>
    </div>
  );
}
