'use client';

import { useEffect, useMemo } from 'react';
import { TokenSource } from 'livekit-client';
import { type UseSessionReturn, useSession } from '@livekit/components-react';

interface UseVoiceConnectionOptions {
  token: string;
  roomName: string;
}

interface UseVoiceConnectionResult {
  session: UseSessionReturn;
}

export function useVoiceConnection({ token }: UseVoiceConnectionOptions): UseVoiceConnectionResult {
  const serverUrl = process.env.NEXT_PUBLIC_LIVEKIT_URL ?? '';

  const tokenSource = useMemo(() => {
    // roomName and participantName are encoded in the JWT from the backend.
    return TokenSource.literal({
      serverUrl,
      participantToken: token,
    });
  }, [token, serverUrl]);

  const session = useSession(tokenSource);

  useEffect(() => {
    // useSession does not auto-connect — start() must be called explicitly.
    // We connect on mount and clean up on unmount.
    session
      .start()
      .catch((err: unknown) =>
        console.error('[useVoiceConnection] Failed to connect to LiveKit:', err)
      );
    return () => {
      session.end().catch(() => {});
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // intentionally run once — reconnecting on session reference change would disconnect

  return { session };
}
