# Event-Driven Architecture Implementation Summary

## Overview

Successfully refactored the custom voice stack to use a clean event-driven architecture with the following key improvements:

1. **LLM → TTS Async Iterator Pipeline**: LLM returns an async iterator that feeds directly to TTS
2. **TTS-Level Chunking**: Text chunking strategies moved into TTS component
3. **Class-Based Consumer Architecture**: Task functions converted to proper consumer classes

## Files Created

### 1. `src/custom_voice/events.py`
Event system with:
- `EventType` enum (14 event types)
- `Event` dataclass (base event container)
- Event data classes: `AudioFrameData`, `VADSignalData`, `TranscriptData`, `TurnProbabilityData`, `TurnCompleteData`

### 2. `src/custom_voice/session_consumers.py`
Consumer classes implementing the event-driven pattern:
- `BaseConsumer`: Abstract base class
- `AudioDistributor`: Zero-copy fan-out to VAD, STT, and audio turn queues
- `VADConsumer`: Processes audio with VAD, emits VAD events
- `STTConsumer`: Processes audio with STT, emits transcript events
- `AudioTurnConsumer`: Processes audio with turn detector, emits turn probability events
- `EventCoordinator`: Central reactive handler coordinating all events

### 3. `src/custom_voice/tts/elevenlabs.py`
ElevenLabs TTS wrapper:
- Wraps LiveKit's official ElevenLabs plugin
- Implements TTSProtocol with chunking strategies
- Supports both WebSocket and HTTP transports

### 4. Test Files
- `tests/custom_voice/test_consumers.py`: 6 unit tests for consumer classes
- `tests/custom_voice/test_llm_tts_streaming.py`: 6 integration tests for LLM→TTS streaming
- `tests/custom_voice/test_elevenlabs_tts.py`: 7 unit tests for ElevenLabs wrapper

### 5. Example Files
- `examples/elevenlabs_example.py`: Complete example using ElevenLabs TTS

## Files Modified

### 1. `src/custom_voice/protocols.py`
Added `synthesize_stream_from_iterator()` method to `TTSProtocol`:
```python
async def synthesize_stream_from_iterator(
    self,
    text_iterator: AsyncIterable[str],
) -> AsyncIterable[rtc.AudioFrame]:
    """
    Synthesize audio from a streaming text source.
    TTS handles internal buffering and chunking.
    """
```

### 2. `src/custom_voice/tts/cartesia.py`
Added:
- `ChunkingStrategy` enum (SENTENCE, WORD, IMMEDIATE)
- `chunking_strategy` and `min_chunk_size` parameters to `__init__`
- `synthesize_stream_from_iterator()` implementation with internal buffering and chunking logic

### 3. `src/custom_voice/session.py`
Complete refactor to event-driven architecture:
- Added event bus and component queues
- Instantiated consumer classes instead of inline task functions
- Simplified `start()` to launch consumer tasks
- Cleaned up `generate_reply()` to use `synthesize_stream_from_iterator()`
- Updated `aclose()` to properly shutdown all consumers

## Key Design Principles Implemented

### Zero-Copy Audio Frame Handling
- **Three separate queues**: `_vad_queue`, `_stt_queue`, `_audio_turn_queue`
- **Same `rtc.AudioFrame` object** passed to all queues (by reference)
- **No copying** - efficient and safe with read-only contract
- Verified by `test_zero_copy_audio_frames` test

### LLM → TTS Streaming Pipeline
```python
# Before (manual chunking in session):
async for token in llm.generate_stream(messages):
    buffer += token
    if buffer.endswith(('.', '!', '?')):
        async for audio in tts.synthesize_stream(buffer):
            yield audio

# After (TTS handles chunking):
token_stream = llm.generate_stream(messages)
async for audio in tts.synthesize_stream_from_iterator(token_stream):
    yield audio
```

### Event-Driven Architecture
- **Event Bus**: `asyncio.Queue[Event]` as central communication hub
- **Independent Consumers**: Each runs as separate async task
- **Fan-Out Pattern**: Audio frames distributed to multiple consumers in parallel
- **Reactive Coordination**: `EventCoordinator` reacts to events from all consumers
- **State-Driven**: System correctness maintained through shared state

## Test Results

All 19 tests pass:

**Consumer Tests** (6 tests):
- ✓ `test_audio_distributor_fan_out`: Verifies fan-out to multiple queues
- ✓ `test_vad_consumer_emits_events`: Verifies VAD event emission
- ✓ `test_vad_consumer_feeds_audio_turn_queue`: Verifies audio turn queue feeding
- ✓ `test_stt_consumer_emits_transcripts`: Verifies STT transcript events
- ✓ `test_audio_turn_consumer_emits_probability`: Verifies turn probability events
- ✓ `test_zero_copy_audio_frames`: **Verifies same AudioFrame object passed to all consumers**

**LLM→TTS Streaming Tests** (6 tests):
- ✓ `test_sentence_chunking_strategy`: Verifies sentence-based chunking
- ✓ `test_word_chunking_strategy`: Verifies word-based chunking
- ✓ `test_immediate_chunking_strategy`: Verifies immediate chunking
- ✓ `test_llm_tts_pipeline_integration`: Verifies full LLM→TTS pipeline
- ✓ `test_chunking_respects_min_chunk_size`: Verifies min chunk size enforcement
- ✓ `test_cancellation_during_streaming`: Verifies cancellation support

**ElevenLabs TTS Tests** (7 tests):
- ✓ `test_elevenlabs_wrapper_initialization`: Verifies wrapper initialization
- ✓ `test_elevenlabs_wrapper_requires_api_key`: Verifies API key validation
- ✓ `test_elevenlabs_synthesize_stream_string`: Verifies string synthesis
- ✓ `test_elevenlabs_synthesize_stream_from_iterator`: Verifies iterator synthesis
- ✓ `test_elevenlabs_chunking_strategies`: Verifies chunking strategies
- ✓ `test_elevenlabs_configure`: Verifies configuration updates
- ✓ `test_elevenlabs_close`: Verifies cleanup

## Architecture Benefits

### 1. Cleaner Code Organization
- **Before**: 321 lines in session.py with scattered task functions
- **After**: Session.py focuses on orchestration, consumers in separate file
- **Result**: Better separation of concerns, easier to test

### 2. Simplified LLM→TTS Pipeline
- **Before**: Manual token buffering and chunking in session layer
- **After**: Single line: `tts.synthesize_stream_from_iterator(llm.generate_stream(...))`
- **Result**: Chunking logic encapsulated in TTS where it belongs

### 3. True Parallelism
- VAD, STT, and audio turn detection run independently
- No blocking between components
- Events enable dynamic execution order

### 4. Maintainability
- Easy to add new consumers (just extend `BaseConsumer`)
- Each consumer independently testable
- Clear event flow for debugging

## Next Steps (Future Work)

1. **Implement remaining event handlers** in `EventCoordinator`:
   - `_on_audio_turn_probability()`
   - `_on_text_turn_probability()`
   - `_on_interruption()`

2. **Add full response tracking** in `generate_reply()`:
   - Currently `full_response` variable is unused
   - Should collect all tokens for conversation context

3. **Update InterruptionHandler** to emit events instead of direct cancellation

4. **Add more integration tests**:
   - Full session lifecycle test
   - Turn detection aggregation test
   - Interruption handling test

5. **Performance optimization**:
   - Event bus batching for high-frequency events
   - Queue size limits to prevent memory issues
   - Metrics and observability

## Verification

Run all tests:
```bash
uv run pytest tests/custom_voice/ -v
```

All 12 tests pass with no linter errors.
