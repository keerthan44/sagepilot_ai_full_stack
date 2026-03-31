'use client';

import { useState } from 'react';
import { AgentSelector } from '@/features/voice/components/AgentSelector';
import { ProviderSelector } from '@/features/voice/components/ProviderSelector';
import { StartCallButton } from '@/features/voice/components/StartCallButton';

const TTS_OPTIONS = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'elevenlabs', label: 'ElevenLabs' },
  { value: 'deepgram', label: 'Deepgram' },
];

const STT_OPTIONS = [
  { value: 'deepgram', label: 'Deepgram' },
  { value: 'openai', label: 'OpenAI Whisper' },
  { value: 'assemblyai', label: 'AssemblyAI' },
];

export default function HomePage() {
  const [agentName, setAgentName] = useState('assistant');
  const [ttsProvider, setTtsProvider] = useState('openai');
  const [sttProvider, setSttProvider] = useState('deepgram');

  const payload = {
    agent: { name: agentName },
    voice: { tts_provider: ttsProvider, stt_provider: sttProvider },
    llm: {},
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

        <StartCallButton payload={payload} />
      </div>
    </div>
  );
}
