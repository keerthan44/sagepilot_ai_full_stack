'use client';

import type { AgentState } from '@livekit/components-react';
import type { TrackReferenceOrPlaceholder } from '@livekit/components-react';
import { AgentAudioVisualizerBar } from '@/components/agents-ui/agent-audio-visualizer-bar';

interface AudioVisualizerProps {
  state: AgentState;
  audioTrack?: TrackReferenceOrPlaceholder;
  barCount?: number;
}

export function AudioVisualizer({ state, audioTrack, barCount = 5 }: AudioVisualizerProps) {
  let size: 'icon' | 'sm' | 'md' | 'lg' | 'xl' = 'xl';

  if (barCount <= 5) {
    size = 'xl';
  } else if (barCount <= 10) {
    size = 'lg';
  } else if (barCount <= 15) {
    size = 'md';
  } else if (barCount <= 30) {
    size = 'sm';
  }

  return (
    <AgentAudioVisualizerBar
      size={size}
      state={state}
      audioTrack={audioTrack}
      barCount={barCount}
      className="h-[112px]"
    />
  );
}
