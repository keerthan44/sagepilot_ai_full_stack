'use client';

import { useSessionDetail } from '@/features/voice/hooks/useSessionDetail';
import type { TranscriptEntry } from '@/features/voice/types';
import {
  sessionVoiceProviderLabels,
  sessionVoiceSttTtsConfigs,
} from '@/features/voice/voice-call-config';

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
  const { session, loading, error, transcriptLoading } = useSessionDetail(sessionId);

  if (loading && !session) {
    return <p className="text-muted-foreground text-sm">Loading session…</p>;
  }

  if (error && !session) {
    return <p className="text-sm text-red-500">{error}</p>;
  }

  if (!session) {
    return <p className="text-muted-foreground text-sm">Session not found.</p>;
  }

  const transcript = session.transcript ?? [];
  const { stt, tts, llm } = sessionVoiceProviderLabels(session.config);
  const { sttConfig, ttsConfig, llmConfig } = sessionVoiceSttTtsConfigs(session.config);

  function humanize(text: string): string {
    if (!text) return '';

    return (
      text
        // split camelCase -> camel Case
        .replace(/([a-z])([A-Z])/g, '$1 $2')
        // replace _ and - with space
        .replace(/[_-]+/g, ' ')
        // lowercase everything first
        .toLowerCase()
        // capitalize each word
        .replace(/\b\w/g, (c) => c.toUpperCase())
        .trim()
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {error ? (
        <p className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-600 dark:text-red-400">
          {error}
        </p>
      ) : null}

      <div className="flex flex-col gap-1">
        <h2 className="text-lg font-semibold">{humanize(session.agent_name)}</h2>
        <p className="text-muted-foreground text-xs">
          {new Date(session.created_at).toLocaleString()}
        </p>
      </div>

      <div className="border-border bg-muted/30 flex flex-col gap-4 rounded-lg border px-4 py-3 text-sm">
        <div>
          <p className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">LLM</p>
          <p className="text-foreground mt-0.5 font-medium">{llm}</p>
          {llmConfig && Object.keys(llmConfig).length > 0 ? (
            <pre className="border-border bg-background/80 text-muted-foreground mt-2 max-h-40 overflow-auto rounded-md border p-2 font-mono text-xs">
              {JSON.stringify(llmConfig, null, 2)}
            </pre>
          ) : (
            <p className="text-muted-foreground mt-1 text-xs">No LLM options in session payload.</p>
          )}
        </div>
        <div>
          <p className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">
            Speech to text
          </p>
          <p className="text-foreground mt-0.5 font-medium">{stt}</p>
          {sttConfig && Object.keys(sttConfig).length > 0 ? (
            <pre className="border-border bg-background/80 text-muted-foreground mt-2 max-h-40 overflow-auto rounded-md border p-2 font-mono text-xs">
              {JSON.stringify(sttConfig, null, 2)}
            </pre>
          ) : (
            <p className="text-muted-foreground mt-1 text-xs">No STT options in session payload.</p>
          )}
        </div>
        <div>
          <p className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">
            Text to speech
          </p>
          <p className="text-foreground mt-0.5 font-medium">{tts}</p>
          {ttsConfig && Object.keys(ttsConfig).length > 0 ? (
            <pre className="border-border bg-background/80 text-muted-foreground mt-2 max-h-40 overflow-auto rounded-md border p-2 font-mono text-xs">
              {JSON.stringify(ttsConfig, null, 2)}
            </pre>
          ) : (
            <p className="text-muted-foreground mt-1 text-xs">No TTS options in session payload.</p>
          )}
        </div>
      </div>

      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-sm font-semibold">Transcript</h3>
          {transcriptLoading ? (
            <span className="text-muted-foreground flex items-center gap-2 text-xs">
              <span className="border-primary h-3.5 w-3.5 animate-spin rounded-full border-2 border-t-transparent" />
              Fetching transcript…
            </span>
          ) : null}
        </div>

        {transcript.length === 0 && !transcriptLoading ? (
          <p className="text-muted-foreground text-sm">No transcript available.</p>
        ) : null}
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
