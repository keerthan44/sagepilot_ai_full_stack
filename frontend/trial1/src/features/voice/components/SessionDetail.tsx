'use client';

import { useSessionDetail } from '@/features/voice/hooks/useSessionDetail';

interface SessionDetailProps {
  sessionId: string;
}

export function SessionDetail({ sessionId }: SessionDetailProps) {
  const { session, loading, error } = useSessionDetail(sessionId);

  if (loading) {
    return <p className="text-muted-foreground text-sm">Loading session…</p>;
  }

  if (error) {
    return <p className="text-sm text-red-500">{error}</p>;
  }

  if (!session) {
    return <p className="text-muted-foreground text-sm">Session not found.</p>;
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h2 className="text-lg font-semibold">{session.agent_name}</h2>
        <p className="text-muted-foreground text-xs">
          {new Date(session.created_at).toLocaleString()}
        </p>
      </div>

      <div className="flex flex-col gap-3">
        {(session.transcript ?? []).length === 0 && (
          <p className="text-muted-foreground text-sm">No transcript available.</p>
        )}
        {(session.transcript ?? []).map((entry, index) => {
          const isUser = entry.role === 'user';
          return (
            <div key={index} className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
              <div
                className={`max-w-[75%] rounded-2xl px-4 py-2 text-sm ${
                  isUser
                    ? 'bg-primary text-primary-foreground rounded-br-sm'
                    : 'bg-muted text-foreground rounded-bl-sm'
                }`}
              >
                <p className="mb-1 text-xs font-semibold capitalize opacity-70">{entry.role}</p>
                <p>{entry.content}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
