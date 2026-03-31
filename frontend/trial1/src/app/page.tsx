'use client';

import { useState } from 'react';
import { AgentSelector } from '@/features/voice/components/AgentSelector';
import { ProviderSelector } from '@/features/voice/components/ProviderSelector';
import { StartCallButton } from '@/features/voice/components/StartCallButton';

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
          <h2 className="text-base font-semibold">Agent Configuration</h2>
          <AgentSelector value={agentName} onChange={setAgentName} />
        </section>

        <div className="bg-border h-px" />

        <section className="flex flex-col gap-4">
          <h2 className="text-base font-semibold">Voice Configuration</h2>
          <ProviderSelector
            label="TTS Provider"
            name="tts_provider"
            value={ttsProvider}
            onChange={setTtsProvider}
            options={TTS_OPTIONS}
          />
          <ProviderSelector
            label="STT Provider"
            name="stt_provider"
            value={sttProvider}
            onChange={setSttProvider}
            options={STT_OPTIONS}
          />
        </section>

        <div className="bg-border h-px" />

        <section className="flex flex-col gap-4">
          <h2 className="text-base font-semibold">LLM Configuration</h2>
          <ProviderSelector
            label="LLM Provider - Fixed To OpenAI for now"
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
