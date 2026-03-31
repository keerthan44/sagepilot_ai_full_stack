'use client';

import { useRouter } from 'next/navigation';
import { useStartSession } from '@/features/voice/hooks/useStartSession';
import type { StartSessionPayload } from '@/features/voice/types';

interface StartCallButtonProps {
  payload: StartSessionPayload;
}

export function StartCallButton({ payload }: StartCallButtonProps) {
  const router = useRouter();
  const { startSession, loading, error } = useStartSession();

  async function handleClick() {
    const result = await startSession(payload);
    if (result) {
      const params = new URLSearchParams({
        token: result.token,
        room_name: result.room_name,
      });
      router.push(`/call/${result.session_id}?${params.toString()}`);
    }
  }

  return (
    <div className="flex flex-col items-start gap-2">
      <button
        onClick={handleClick}
        disabled={loading}
        className="bg-primary text-primary-foreground rounded-lg px-6 py-2.5 text-sm font-medium transition-opacity hover:opacity-90 disabled:opacity-60"
      >
        {loading ? 'Starting…' : 'Start Call'}
      </button>
      {error && <p className="text-sm text-red-500">{error}</p>}
    </div>
  );
}
