# Custom Voice Stack

A modular voice agent system with swappable components for STT, LLM, TTS, VAD, and turn detection. Uses LiveKit only for room management and worker spawning.

## Architecture

The custom voice stack implements a pipeline-based architecture where:

1. **Audio Input** → **VAD** → **Parallel Processing**:
   - Branch 1: Audio Turn Detector (optional)
   - Branch 2: STT
2. **STT** → **Text Turn Detector** (optional, sequential)
3. **Turn Decision** → **LLM** → **TTS** → **Audio Output**

## Components

### Core Protocols (`protocols.py`)
- `STTProtocol`: Speech-to-text interface
- `LLMProtocol`: Language model interface
- `TTSProtocol`: Text-to-speech interface
- `VADProtocol`: Voice activity detection interface
- `AudioTurnDetectorProtocol`: Audio-based turn detection
- `TextTurnDetectorProtocol`: Text-based turn detection with conversation context

### Implementations

#### STT (`stt/`)
- **Deepgram**: WebSocket and HTTP streaming support
- Easily extensible for other providers (Whisper, Google, etc.)

#### LLM (`llm/`)
- **OpenAI**: Streaming and tool support
- Easily extensible for other providers (Anthropic, Google, etc.)

#### TTS (`tts/`)
- **Cartesia**: WebSocket and HTTP streaming support (simplified implementation)
- Easily extensible for other providers (ElevenLabs, OpenAI, etc.)

#### VAD (`vad/`)
- **Silero**: Wraps LiveKit's Silero VAD plugin

#### Turn Detection (`turn_detection/`)
- **VAD-based**: Audio-only turn detection using silence duration
- **EOU Text**: Text-based turn detection with conversation context (4 turns)
- **Aggregator**: Combines audio and text signals with configurable strategies

### Orchestration

#### CustomAgentSession (`session.py`)
Main orchestration layer that:
- Manages pipeline lifecycle
- Coordinates audio flow through components
- Handles turn detection and endpointing
- Manages interruptions
- Maintains conversation history

#### Audio Pipeline (`audio_pipeline.py`)
- Routes audio between components
- Handles format conversions and resampling
- Manages audio buffers

#### Interruption Handler (`interruption.py`)
- Monitors VAD during agent speaking
- Detects valid interruptions
- Handles AEC warmup and false interruptions
- Cancels ongoing TTS/LLM generation

#### Conversation Context (`context.py`)
- Maintains conversation history
- Provides sliding window for turn detectors
- Converts to LLM message format

## Configuration

All components are configured through dataclasses in `config.py`:

```python
from custom_voice import (
    VoiceStackConfig,
    STTConfig,
    LLMConfig,
    TTSConfig,
    VADConfig,
    TurnDetectionConfig,
    AudioTurnDetectorConfig,
    TextTurnDetectorConfig,
)

config = VoiceStackConfig(
    stt=STTConfig(
        provider="deepgram",
        model="nova-3",
        language="multi",
        transport="websocket",
    ),
    llm=LLMConfig(
        provider="openai",
        model="gpt-4.1-mini",
    ),
    tts=TTSConfig(
        provider="cartesia",
        model="sonic-3",
        voice="your-voice-id",
    ),
    vad=VADConfig(
        provider="silero",
        threshold=0.5,
    ),
    turn_detection=TurnDetectionConfig(
        audio_detector=AudioTurnDetectorConfig(
            type="vad",
            silence_duration=0.8,
        ),
        text_detector=TextTurnDetectorConfig(
            type="eou",
            context_window_turns=4,
        ),
        aggregation_strategy="weighted",
        weights={"audio": 0.4, "text": 0.6},
    ),
)
```

## Usage

### Basic Example

```python
from custom_voice import (
    CustomAgentSession,
    create_stt,
    create_llm,
    create_tts,
    create_vad,
    create_turn_detector,
)

# Create components
stt = create_stt("deepgram", model="nova-3", language="multi")
llm = create_llm("openai", model="gpt-4.1-mini")
tts = create_tts("cartesia", model="sonic-3", voice="your-voice-id")
vad = create_vad("silero")

# Optional turn detectors
audio_turn_detector = create_turn_detector("vad", silence_duration=0.8)
text_turn_detector = create_turn_detector("eou", context_window_turns=4)

# Create session
session = CustomAgentSession(
    stt=stt,
    llm=llm,
    tts=tts,
    vad=vad,
    audio_turn_detector=audio_turn_detector,
    text_turn_detector=text_turn_detector,
)

# Start session
await session.start(room, instructions="You are a helpful assistant.")

# Generate response
await session.generate_reply("Hello!")
```

## Turn Detection Scenarios

### 1. No Turn Detector (Default Endpointing)
```python
TurnDetectionConfig(
    audio_detector=None,
    text_detector=None,
    min_endpointing_delay=0.5,
    max_endpointing_delay=3.0,
)
```

### 2. Audio-Only Turn Detection
```python
TurnDetectionConfig(
    audio_detector=AudioTurnDetectorConfig(type="vad", silence_duration=0.8),
    text_detector=None,
)
```

### 3. Text-Only Turn Detection
```python
TurnDetectionConfig(
    audio_detector=None,
    text_detector=TextTurnDetectorConfig(type="eou", context_window_turns=4),
)
```

### 4. Both Audio and Text (Aggregation)
```python
TurnDetectionConfig(
    audio_detector=AudioTurnDetectorConfig(type="vad"),
    text_detector=TextTurnDetectorConfig(type="eou"),
    aggregation_strategy="weighted",
    weights={"audio": 0.4, "text": 0.6},
)
```

## Transport Flexibility

STT and TTS components support both WebSocket and HTTP transports:

```python
# WebSocket (default, lower latency)
stt = create_stt("deepgram", transport="websocket", ...)

# HTTP (fallback, simpler)
stt = create_stt("deepgram", transport="http", ...)
```

## Adding New Providers

To add a new provider, implement the corresponding protocol and update the factory:

1. Create implementation in appropriate directory (e.g., `stt/whisper.py`)
2. Implement the protocol interface (e.g., `STTProtocol`)
3. Update factory (e.g., `stt/factory.py`)

## Limitations (Prototype)

This is a simplified prototype. Production implementation would need:

- [ ] Robust error handling and recovery
- [ ] Event emission for observability
- [ ] Tool execution support
- [ ] Preemptive generation
- [ ] Better streaming STT integration
- [ ] Room connection management
- [ ] Participant tracking
- [ ] More sophisticated state management
- [ ] Metrics and telemetry
- [ ] Complete Cartesia TTS implementation (current is simplified)

## Dependencies

Required packages:
- `livekit-agents[silero,turn-detector]~=1.4`
- `deepgram-sdk>=3.0`
- `openai>=1.0`
- `aiohttp`
- `numpy>=1.24`

Optional:
- `cartesia` (if using Cartesia TTS)
