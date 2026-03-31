'use client';

import Link from 'next/link';
import { useSessions } from '@/features/voice/hooks/useSessions';

export function SessionList() {
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
      {sessions.map((session) => (
        <li key={session.id}>
          <Link
            href={`/sessions/${session.id}`}
            className="border-border bg-card hover:bg-accent block rounded-lg border px-4 py-3 transition-colors"
          >
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">{session.agent_name}</span>
              <span className="text-muted-foreground text-xs">
                {new Date(session.created_at).toLocaleString()}
              </span>
            </div>
            <p className="text-muted-foreground mt-1 text-xs">
              {(session.transcript ?? []).length} message
              {(session.transcript ?? []).length !== 1 ? 's' : ''}
            </p>
          </Link>
        </li>
      ))}
    </ul>
  );
}
