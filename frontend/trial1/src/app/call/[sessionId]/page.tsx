'use client';

import { use } from 'react';
import { useRouter } from 'next/navigation';
import { useSearchParams } from 'next/navigation';
import {
  type AgentState,
  useAgent,
  useLocalParticipant,
  useSessionContext,
} from '@livekit/components-react';
import { AgentSessionProvider } from '@/components/agents-ui/agent-session-provider';
import { AgentStateIndicator } from '@/features/voice/components/AgentStateIndicator';
import { AudioVisualizer } from '@/features/voice/components/AudioVisualizer';
import { useVoiceConnection } from '@/features/voice/hooks/useVoiceConnection';
import type { VoiceConnectionState } from '@/features/voice/types';

function mapAgentState(agentState: AgentState): VoiceConnectionState {
  switch (agentState) {
    case 'speaking':
      return 'speaking';
    case 'listening':
    case 'thinking':
    case 'idle':
      return 'listening';
    default:
      return 'connecting';
  }
}

/**
 * Rendered inside AgentSessionProvider so LiveKit context hooks work correctly.
 */
function CallView({ sessionId }: { sessionId: string }) {
  const router = useRouter();
  const session = useSessionContext();
  const agent = useAgent();
  const { isMicrophoneEnabled, localParticipant } = useLocalParticipant();

  const agentConnected = agent.isConnected;
  const state = mapAgentState(agent.state);

  async function handleEndCall() {
    await session.end();
    router.push(`/sessions/${sessionId}`);
  }

  function handleToggleMic() {
    localParticipant.setMicrophoneEnabled(!isMicrophoneEnabled);
  }

  return (
    <div className="flex flex-col items-center justify-center gap-10 py-20">
      <div className="text-center">
        <h1 className="text-2xl font-bold tracking-tight">Active Call</h1>
        <p className="text-muted-foreground mt-1 font-mono text-sm">{sessionId}</p>
      </div>

      {/* Agent state card */}
      <div className="border-border bg-card flex min-h-[160px] flex-col items-center justify-center gap-6 rounded-2xl border px-12 py-10 shadow-sm">
        {agentConnected ? (
          <>
            <AudioVisualizer state={state} barCount={7} />
            <AgentStateIndicator state={state} />
          </>
        ) : (
          <div className="flex flex-col items-center gap-3">
            <span className="border-primary h-8 w-8 animate-spin rounded-full border-2 border-t-transparent" />
            <p className="text-muted-foreground text-sm">
              {agent.state === 'failed'
                ? 'Agent failed to connect.'
                : 'Waiting for agent to connect…'}
            </p>
          </div>
        )}
      </div>

      {/* Call controls */}
      <div className="flex items-center gap-4">
        {/* Mic toggle */}
        <button
          onClick={handleToggleMic}
          title={isMicrophoneEnabled ? 'Mute microphone' : 'Unmute microphone'}
          className={`flex h-12 w-12 items-center justify-center rounded-full border transition-colors ${
            isMicrophoneEnabled
              ? 'border-border bg-card hover:bg-muted text-foreground'
              : 'border-transparent bg-yellow-500 text-white hover:bg-yellow-400'
          }`}
        >
          {isMicrophoneEnabled ? <MicIcon /> : <MicOffIcon />}
        </button>

        {/* End call */}
        <button
          onClick={handleEndCall}
          title="End call"
          className="flex h-14 w-14 items-center justify-center rounded-full bg-red-500 text-white transition-colors hover:bg-red-400"
        >
          <PhoneOffIcon />
        </button>
      </div>
    </div>
  );
}

// ── Inline SVG icons (no extra deps) ────────────────────────────────────────

function MicIcon() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <line x1="12" x2="12" y1="19" y2="22" />
    </svg>
  );
}

function MicOffIcon() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <line x1="2" x2="22" y1="2" y2="22" />
      <path d="M18.89 13.23A7.12 7.12 0 0 0 19 12v-2" />
      <path d="M5 10v2a7 7 0 0 0 12 5" />
      <path d="M15 9.34V5a3 3 0 0 0-5.68-1.33" />
      <path d="M9 9v3a3 3 0 0 0 5.12 2.12" />
      <line x1="12" x2="12" y1="19" y2="22" />
    </svg>
  );
}

function PhoneOffIcon() {
  return (
    <svg
      width="22"
      height="22"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M10.68 13.31a16 16 0 0 0 3.41 2.6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7 2 2 0 0 1 1.72 2v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07" />
      <path d="M14.5 2.81a19.93 19.93 0 0 0-12.48 12" />
      <line x1="2" x2="22" y1="2" y2="22" />
    </svg>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

interface CallPageProps {
  params: Promise<{ sessionId: string }>;
}

export default function CallPage({ params }: CallPageProps) {
  const { sessionId } = use(params);
  const searchParams = useSearchParams();

  const token = searchParams.get('token') ?? '';
  const roomName = searchParams.get('room_name') ?? '';

  const { session } = useVoiceConnection({ token, roomName });

  return (
    <AgentSessionProvider session={session}>
      <CallView sessionId={sessionId} />
    </AgentSessionProvider>
  );
}
