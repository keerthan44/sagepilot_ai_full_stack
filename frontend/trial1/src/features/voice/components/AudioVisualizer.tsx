'use client';

import { useEffect, useRef } from 'react';
import type { VoiceConnectionState } from '@/features/voice/types';

interface AudioVisualizerProps {
  state: VoiceConnectionState;
  barCount?: number;
}

export function AudioVisualizer({ state, barCount = 5 }: AudioVisualizerProps) {
  const barsRef = useRef<(HTMLDivElement | null)[]>([]);
  const animationRef = useRef<number | null>(null);

  const isActive = state === 'listening' || state === 'speaking';

  useEffect(() => {
    if (!isActive) {
      barsRef.current.forEach((bar) => {
        if (bar) bar.style.transform = 'scaleY(0.15)';
      });
      return;
    }

    function animate() {
      barsRef.current.forEach((bar) => {
        if (!bar) return;
        const scale = state === 'speaking' ? 0.2 + Math.random() * 0.8 : 0.1 + Math.random() * 0.4;
        bar.style.transform = `scaleY(${scale})`;
      });
      animationRef.current = requestAnimationFrame(() => {
        setTimeout(animate, 80);
      });
    }

    animate();

    return () => {
      if (animationRef.current) cancelAnimationFrame(animationRef.current);
    };
  }, [isActive, state]);

  return (
    <div
      className="flex items-center justify-center gap-1"
      style={{ height: '64px' }}
      aria-hidden="true"
    >
      {Array.from({ length: barCount }).map((_, i) => (
        <div
          key={i}
          ref={(el) => {
            barsRef.current[i] = el;
          }}
          className="bg-primary w-2 rounded-full transition-transform"
          style={{
            height: '48px',
            transform: 'scaleY(0.15)',
            transitionDuration: '80ms',
            transitionTimingFunction: 'ease-in-out',
            transitionDelay: `${i * 10}ms`,
          }}
        />
      ))}
    </div>
  );
}
