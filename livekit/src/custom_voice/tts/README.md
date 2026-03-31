# Text-to-Speech (TTS) Module

This module provides TTS implementations for the custom voice stack with support for multiple providers.

## Supported Providers

### 1. Cartesia TTS

Custom implementation supporting both WebSocket and HTTP transports.

```python
from custom_voice.tts import CartesiaTTS, ChunkingStrategy

tts = CartesiaTTS(
    model="sonic-3",
    voice="your-voice-id",
    transport="websocket",  # or "http"
    chunking_strategy=ChunkingStrategy.SENTENCE,
    min_chunk_size=10,
)
```

### 2. ElevenLabs TTS

Wrapper around LiveKit's official ElevenLabs plugin.

```python
from custom_voice.tts import ElevenLabsTTSWrapper, ChunkingStrategy

tts = ElevenLabsTTSWrapper(
    voice_id="l7kNoIfnJKPg7779LI2t",
    model="eleven_turbo_v2_5",
    chunking_strategy=ChunkingStrategy.SENTENCE,
    min_chunk_size=10,
    auto_mode=True,
)
```

## Chunking Strategies

All TTS implementations support configurable chunking strategies for streaming text:

### SENTENCE (Default)
- Buffers tokens until punctuation boundary (`.`, `!`, `?`, `\n`)
- Best balance between latency and naturalness
- Recommended for most use cases

```python
tts = CartesiaTTS(
    ...,
    chunking_strategy=ChunkingStrategy.SENTENCE,
    min_chunk_size=10,
)
```

### WORD
- Buffers tokens until word boundary (space)
- Lower latency than SENTENCE
- May sound slightly less natural

```python
tts = CartesiaTTS(
    ...,
    chunking_strategy=ChunkingStrategy.WORD,
    min_chunk_size=5,
)
```

### IMMEDIATE
- Sends tokens as soon as `min_chunk_size` is reached
- Lowest latency
- May produce robotic or cut-off speech

```python
tts = CartesiaTTS(
    ...,
    chunking_strategy=ChunkingStrategy.IMMEDIATE,
    min_chunk_size=20,
)
```

## Factory Function

Use the factory function for easy instantiation:

```python
from custom_voice import create_tts
from custom_voice.tts import ChunkingStrategy

# Cartesia
tts = create_tts(
    provider="cartesia",
    model="sonic-3",
    voice="your-voice-id",
    transport="websocket",
)

# ElevenLabs
tts = create_tts(
    provider="elevenlabs",
    voice="l7kNoIfnJKPg7779LI2t",
    model="eleven_turbo_v2_5",
    chunking_strategy=ChunkingStrategy.SENTENCE,
)
```

## Streaming Methods

### `synthesize_stream(text: str)`
Synthesize a complete string with streaming output.

```python
async for audio_frame in tts.synthesize_stream("Hello world"):
    # Process audio frame
    pass
```

### `synthesize_stream_from_iterator(text_iterator: AsyncIterable[str])`
Synthesize from a streaming text source (e.g., LLM tokens).

The TTS handles internal buffering and chunking based on the configured strategy.

```python
# LLM generates tokens
token_stream = llm.generate_stream(messages)

# TTS handles chunking internally
async for audio_frame in tts.synthesize_stream_from_iterator(token_stream):
    # Process audio frame
    pass
```

This method is designed for **LLM → TTS streaming pipelines** where you want to start speaking as soon as the first sentence is complete, without waiting for the full LLM response.

## Adding New TTS Providers

To add a new TTS provider:

1. Create a new file in `src/custom_voice/tts/` (e.g., `openai.py`)
2. Extend `BaseTTS` and implement the required methods:
   - `synthesize_stream()`
   - `synthesize_stream_from_iterator()`
   - `synthesize()`
3. Add to factory in `factory.py`
4. Add tests in `tests/custom_voice/test_<provider>_tts.py`

Example structure:

```python
from .base import BaseTTS

class NewProviderTTS(BaseTTS):
    def __init__(self, *, voice: str, model: str, **kwargs):
        super().__init__(model=model, voice=voice, sample_rate=24000)
        # Provider-specific initialization
    
    async def synthesize_stream(self, text: str | AsyncIterable[str]) -> AsyncIterable[rtc.AudioFrame]:
        # Implementation
        ...
    
    async def synthesize_stream_from_iterator(self, text_iterator: AsyncIterable[str]) -> AsyncIterable[rtc.AudioFrame]:
        # Implementation with chunking
        ...
    
    async def synthesize(self, text: str) -> list[rtc.AudioFrame]:
        # Implementation
        ...
```

## Environment Variables

- `CARTESIA_API_KEY`: Required for Cartesia TTS
- `ELEVEN_API_KEY`: Required for ElevenLabs TTS

Set these in your `.env.local` file or environment.
