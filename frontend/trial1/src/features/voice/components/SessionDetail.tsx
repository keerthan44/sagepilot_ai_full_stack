'use client';

import { useSessionDetail } from '@/features/voice/hooks/useSessionDetail';
import type { TranscriptEntry } from '@/features/voice/types';

interface SessionDetailProps {
  sessionId: string;
}

function TranscriptMessage({
  entry,
  previousEntries,
}: {
  entry: TranscriptEntry;
  previousEntries: TranscriptEntry[];
}) {
  const { role, content } = entry;

  // User messages
  if (role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="bg-primary text-primary-foreground max-w-[75%] rounded-2xl rounded-br-sm px-4 py-2 text-sm">
          <p className="mb-1 text-xs font-semibold capitalize opacity-70">User</p>
          <p>{content}</p>
        </div>
      </div>
    );
  }

  // Assistant messages — check if preceded by tool_call + tool_result
  if (role === 'assistant') {
    // Look back for tool_call and tool_result that happened just before this assistant message
    let toolCall: TranscriptEntry | undefined;
    let toolResult: TranscriptEntry | undefined;

    if (previousEntries.length >= 2) {
      const prev1 = previousEntries[previousEntries.length - 1];
      const prev2 = previousEntries[previousEntries.length - 2];

      if (prev1?.role === 'tool_result' && prev2?.role === 'tool_call') {
        toolCall = prev2;
        toolResult = prev1;
      }
    }

    const toolName = toolCall?.tool_calls?.[0]?.name ?? toolCall?.metadata?.name;
    const toolArgs = toolCall?.tool_calls?.[0]?.args;
    const resultContent = toolResult?.content;

    return (
      <div className="flex justify-start">
        <div className="bg-muted text-foreground max-w-[75%] rounded-2xl rounded-bl-sm px-4 py-2.5 text-sm">
          <p className="mb-1.5 text-xs font-semibold capitalize opacity-70">Assistant</p>

          {/* Tool call/result summary */}
          {toolName && (
            <div className="bg-background/50 border-border/50 mb-2.5 rounded-lg border px-3 py-2 text-xs">
              <p className="text-muted-foreground mb-1 font-semibold">
                Tool called: <span className="text-primary font-mono font-normal">{toolName}</span>
                {toolArgs && Object.keys(toolArgs).length > 0 && (
                  <span className="text-muted-foreground ml-1 font-mono font-normal">
                    ({JSON.stringify(toolArgs)})
                  </span>
                )}
              </p>
              {resultContent && (
                <p className="text-foreground font-mono">
                  <span className="text-muted-foreground font-sans font-semibold">Result:</span>{' '}
                  {resultContent}
                </p>
              )}
            </div>
          )}

          {/* Assistant response */}
          <p>{content}</p>
        </div>
      </div>
    );
  }

  // Skip tool_call and tool_result entries — they're merged into the assistant message
  if (role === 'tool_call' || role === 'tool_result') {
    return null;
  }

  return null;
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

  const transcript = session.transcript ?? [];
  function humanize(text: string): string {
  if (!text) return ""

  return text
    // split camelCase -> camel Case
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    // replace _ and - with space
    .replace(/[_-]+/g, " ")
    // lowercase everything first
    .toLowerCase()
    // capitalize each word
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .trim()
}

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h2 className="text-lg font-semibold">{humanize(session.agent_name)}</h2>
        <p className="text-muted-foreground text-xs">
          {new Date(session.created_at).toLocaleString()}
        </p>
      </div>

      <div className="flex flex-col gap-3">
        {transcript.length === 0 && (
          <p className="text-muted-foreground text-sm">No transcript available.</p>
        )}
        {transcript.map((entry, index) => (
          <TranscriptMessage
            key={index}
            entry={entry}
            previousEntries={transcript.slice(0, index)}
          />
        ))}
      </div>
    </div>
  );
}
