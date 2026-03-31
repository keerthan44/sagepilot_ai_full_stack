# Tradeoffs and Next Steps

This document covers what was simplified in this prototype, the reasoning behind those choices, and what a production version would look like.

---

## What Was Simplified

### Provider failover — skipped

There is no failover between STT or TTS providers. If a Deepgram WebSocket drops mid-utterance, the session will error. This was intentionally left out because the abstraction layer already makes it straightforward to add later (see below), and adding it in the prototype would have introduced complexity around state management (mid-stream handoff, partial transcript reconciliation) that is out of scope for a working demo.

### Error handling

Error handling is minimal. Exceptions in consumers propagate up to the session and will typically tear down the session. A production system would distinguish between transient errors (network blip → retry), provider errors (bad API key → surface to operator), and logic errors (bug → alert).

### Audio-level turn detection — half-written, not usable

The codebase contains scaffolding for a third turn detection path that would detect end-of-utterance from the audio signal itself, using VAD probability rather than waiting for STT to produce text. The following pieces are stubbed out:

- `_audio_turn_queue` — a queue that would carry `(AudioFrame, vad_probability)` tuples
- `AudioTurnConsumer` — a consumer class that reads from that queue and calls an `AudioTurnDetectorProtocol`
- `VADBasedTurnDetector` — an implementation that ramps a probability to 1.0 after a configurable silence duration
- Hooks in `VADConsumer` and `CustomAgentSession` to wire them together

However, the end-to-end integration was never completed and the path has never been tested. In the current working system, `audio_turn_queue` is `None`, `AudioTurnConsumer` is never started, and `_audio_turn_probability` is always `0.0`. The architecture doc documents only the working paths.

### VAD provider

VAD is hard-coded to Silero. It is not config-driven like STT and TTS. A production system would apply the same factory pattern.

---

## Provider Failover — How It Would Be Built

### Option 1 — Forked parallel streams (lowest latency)

The lowest-latency approach is to send the same audio stream to two providers simultaneously and use whichever responds first. This costs more (two providers billed per utterance) but eliminates provider latency variance from the user experience.

```
AudioFrame
  ├─► DeepgramSTT.recognize_stream  ──┐
  │                                   ├─► race: take first final transcript
  └─► AssemblyAISTT.recognize_stream ─┘
```

Implementation sketch: a `RacingSTT` wrapper that satisfies `STTProtocol`, fans the input `AsyncIterable[AudioFrame]` to two internal queues, runs both `recognize_stream` calls concurrently, and yields from whichever produces a `TranscriptSegment` with `is_final=True` first — then cancels the other.

### Option 2 — Sequential fallback (lower cost)

A simpler `FallbackSTT` wrapper tries the primary provider and, if it raises within a timeout window, transparently switches to the secondary. Because `recognize_stream` is a streaming call, the fallback needs to buffer the audio frames it has already consumed so the secondary can replay them from the start of the utterance.

```python
class FallbackSTT(BaseSTT):
    def __init__(self, primary: STTProtocol, fallback: STTProtocol): ...

    async def recognize_stream(
        self, audio_stream: AsyncIterable[rtc.AudioFrame]
    ) -> AsyncIterable[TranscriptSegment]:
        buffer = []
        try:
            async for frame in audio_stream:
                buffer.append(frame)
                # forward to primary ...
                # yield results from primary ...
        except ProviderError:
            # replay buffer into fallback
            async for segment in self.fallback.recognize_stream(iter(buffer)):
                yield segment
```

The same wrapper pattern applies identically to TTS via `TTSProtocol`. Because both STT and TTS hide behind the same interface, the session and consumers require zero changes — you swap `DeepgramSTT` for `FallbackSTT(DeepgramSTT, AssemblyAISTT)` at construction time in the factory.

### Why the abstraction makes this easy

The protocol layer was designed with exactly this in mind. `STTProtocol` and `TTSProtocol` are structural protocols — any class with the right methods satisfies them. A `FallbackSTT` or `RacingSTT` is just another implementation. It slots into the existing factory, gets wired the same way, and the rest of the system is unaware of the change.

---

## What Would Be Improved Next

- **Provider failover** — `FallbackSTT` and `FallbackTTS` wrappers as described above.
- **Streaming transcript display** — surface `STT_INTERIM_TRANSCRIPT` events to the frontend via a LiveKit data channel or a WebSocket endpoint so users can see what they said.
- **Per-agent TTS voice config** — currently voice is global; agents should carry their own voice identity in `AgentConfig`.
- **Audio turn detection** — complete the `AudioTurnConsumer` path (scaffolding exists but was never integrated or tested). The idea is to run a parallel queue fed by `VADConsumer` that evaluates end-of-utterance from the audio signal directly, independently of STT, so turn decisions can be made faster and without waiting for a final transcript.
- **More LLM providers** — the `LLMProtocol` / `BaseLLM` abstraction already supports adding Anthropic, Gemini, etc. Only `OpenAILLM` is implemented today.
- **Session persistence and replay** — transcripts are saved to Postgres at session end, but there is no replay or analytics UI.
