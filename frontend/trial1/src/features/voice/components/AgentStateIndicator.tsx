'use client';

import type { VoiceConnectionState } from '@/features/voice/types';

interface AgentStateIndicatorProps {
  state: VoiceConnectionState;
}

const STATE_CONFIG: Record<VoiceConnectionState, { label: string; color: string }> = {
  idle: { label: 'Idle', color: 'bg-gray-400' },
  connecting: { label: 'Connecting…', color: 'bg-yellow-400' },
  listening: { label: 'Listening', color: 'bg-green-500' },
  speaking: { label: 'Speaking', color: 'bg-blue-500' },
  thinking: { label: 'Thinking', color: 'bg-purple-500' },
};

export function AgentStateIndicator({ state }: AgentStateIndicatorProps) {
  const { label, color } = STATE_CONFIG[state];

  return (
    <div className="flex items-center gap-2">
      <span
        className={`inline-block h-2.5 w-2.5 rounded-full ${color} ${
          state === 'connecting' ? 'animate-pulse' : ''
        }`}
      />
      <span className="text-foreground text-sm font-medium">{label}</span>
    </div>
  );
}
