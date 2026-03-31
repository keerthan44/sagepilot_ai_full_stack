'use client';

import { use } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { type AgentState, useAgent } from '@livekit/components-react';
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
    // connecting | pre-connect-buffering | initializing | disconnected | failed
    default:
      return 'connecting';
  }
}

/**
 * Rendered inside AgentSessionProvider so useAgent() picks up the SessionProvider context.
 * This is the same pattern used by AgentSessionView_01 in the existing codebase.
 */
function CallView({ sessionId }: { sessionId: string }) {
  // No session arg — reads from the SessionProvider context above
  const agent = useAgent();

  // isConnected is true only when agent.state is 'listening' | 'thinking' | 'speaking'
  // i.e. the remote agent participant is actually present and active in the room.
  const agentConnected = agent.isConnected;
  const state = mapAgentState(agent.state);

  return (
    <div className="flex flex-col items-center justify-center gap-10 py-20">
      <div className="text-center">
        <h1 className="text-2xl font-bold tracking-tight">Active Call</h1>
        <p className="text-muted-foreground mt-1 font-mono text-sm">{sessionId}</p>
      </div>

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

      <Link
        href="/sessions"
        className="text-muted-foreground hover:text-foreground text-sm transition-colors"
      >
        View Sessions →
      </Link>
    </div>
  );
}

interface CallPageProps {
  params: Promise<{ sessionId: string }>;
}

export default function CallPage({ params }: CallPageProps) {
  const { sessionId } = use(params);
  const searchParams = useSearchParams();

  const token = searchParams.get('token') ?? '';
  const roomName = searchParams.get('room_name') ?? '';

  // useVoiceConnection creates the LiveKit session and calls session.start() on mount.
  const { session } = useVoiceConnection({ token, roomName });

  return (
    // AgentSessionProvider wraps with SessionProvider + RoomAudioRenderer.
    // CallView is a child so useAgent() can read from the SessionProvider context.
    <AgentSessionProvider session={session}>
      <CallView sessionId={sessionId} />
    </AgentSessionProvider>
  );
}
