'use client';

import Link from 'next/link';
import { useSessions } from '@/features/voice/hooks/useSessions';
import { sessionVoiceProviderLabels } from '@/features/voice/voice-call-config';

export function SessionList() {
  function humanize(text: string): string {
    if (!text) return '';

    return text
      .replace(/([a-z])([A-Z])/g, '$1 $2')
      .replace(/[_-]+/g, ' ')
      .toLowerCase()
      .replace(/\b\w/g, (c) => c.toUpperCase())
      .trim();
  }

  const { sessions, loading, error } = useSessions();

  if (loading) {
    return <p className="text-muted-foreground text-sm">Loading sessions…</p>;
  }

  if (error) {
    return <p className="text-sm text-red-500">{error}</p>;
  }

  if (sessions.length === 0) {
    return <p className="text-muted-foreground text-sm">No sessions found.</p>;
  }

  return (
    <ul className="flex flex-col gap-3">
      {sessions.map((session) => {
        const { stt, tts } = sessionVoiceProviderLabels(session.config);
        const messageCount = (session.transcript ?? []).length;

        return (
          <li key={session.id}>
            <Link
              href={`/sessions/${session.id}`}
              className="border-border bg-card hover:bg-accent block rounded-lg border px-4 py-3 transition-colors"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-foreground text-sm font-semibold">
                  {humanize(session.agent_name)}
                </span>
                <span className="text-muted-foreground shrink-0 text-xs">
                  {new Date(session.created_at).toLocaleString()}
                </span>
              </div>

              <div className="text-muted-foreground mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs">
                <span>
                  <span className="text-foreground/80 font-medium">STT</span>
                  {': '}
                  {stt}
                </span>
                <span>
                  <span className="text-foreground/80 font-medium">TTS</span>
                  {': '}
                  {tts}
                </span>
              </div>

              <p className="text-muted-foreground border-border mt-2 border-t pt-2 text-xs">
                {messageCount} message{messageCount !== 1 ? 's' : ''} in transcript
              </p>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
