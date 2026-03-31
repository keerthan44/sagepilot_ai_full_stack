"""Tests for event-driven consumer classes."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest
from livekit import rtc

from custom_voice.events import (
    Event,
    EventType,
    TranscriptData,
    VADSignalData,
)
from custom_voice.protocols import TranscriptSegment, VADSignal
from custom_voice.session_consumers import (
    AudioDistributor,
    AudioTurnConsumer,
    STTConsumer,
    VADConsumer,
)


@pytest.fixture
def mock_audio_frame():
    """Create a mock audio frame."""
    audio_data = np.zeros(480, dtype=np.int16)
    return rtc.AudioFrame(
        data=audio_data.tobytes(),
        sample_rate=24000,
        num_channels=1,
        samples_per_channel=480,
    )


@pytest.fixture
def event_bus():
    """Create an event bus."""
    return asyncio.Queue()


@pytest.mark.asyncio
async def test_audio_distributor_fan_out(event_bus, mock_audio_frame):
    """Test AudioDistributor distributes same frame to all queues."""
    vad_queue = asyncio.Queue()
    stt_queue = asyncio.Queue()
    
    mock_pipeline = AsyncMock()
    
    async def mock_input_stream():
        yield mock_audio_frame
    
    mock_pipeline.input_stream = mock_input_stream
    
    distributor = AudioDistributor(
        event_bus,
        mock_pipeline,
        vad_queue,
        stt_queue,
    )
    
    task = asyncio.create_task(distributor.run())
    
    await asyncio.sleep(0.1)
    
    distributor.close()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    
    event = await event_bus.get()
    assert event.type == EventType.AUDIO_FRAME
    assert event.data.frame is mock_audio_frame
    
    vad_frame = await vad_queue.get()
    stt_frame = await stt_queue.get()
    
    assert vad_frame is mock_audio_frame
    assert stt_frame is mock_audio_frame
    assert vad_frame is stt_frame


@pytest.mark.asyncio
async def test_vad_consumer_emits_events(event_bus, mock_audio_frame):
    """Test VADConsumer processes audio and emits VAD events."""
    vad_queue = asyncio.Queue()
    
    mock_vad = AsyncMock()
    mock_vad.process_audio.return_value = VADSignal(
        is_speech=True,
        probability=0.9,
        timestamp=0.0,
    )
    
    consumer = VADConsumer(
        event_bus,
        mock_vad,
        vad_queue,
        audio_turn_queue=None,
    )
    
    await vad_queue.put(mock_audio_frame)
    
    task = asyncio.create_task(consumer.run())
    
    await asyncio.sleep(0.1)
    
    consumer.close()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    
    events = []
    while not event_bus.empty():
        events.append(await event_bus.get())
    
    assert len(events) >= 2
    assert any(e.type == EventType.VAD_INFERENCE_DONE for e in events)
    assert any(e.type == EventType.VAD_START_OF_SPEECH for e in events)


@pytest.mark.asyncio
async def test_vad_consumer_feeds_audio_turn_queue(event_bus, mock_audio_frame):
    """Test VADConsumer feeds audio turn detector queue."""
    vad_queue = asyncio.Queue()
    audio_turn_queue = asyncio.Queue()
    
    mock_vad = AsyncMock()
    mock_vad.process_audio.return_value = VADSignal(
        is_speech=True,
        probability=0.85,
        timestamp=0.0,
    )
    
    consumer = VADConsumer(
        event_bus,
        mock_vad,
        vad_queue,
        audio_turn_queue=audio_turn_queue,
    )
    
    await vad_queue.put(mock_audio_frame)
    
    task = asyncio.create_task(consumer.run())
    
    await asyncio.sleep(0.1)
    
    consumer.close()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    
    frame, prob = await audio_turn_queue.get()
    assert frame is mock_audio_frame
    assert prob == 0.85


@pytest.mark.asyncio
async def test_stt_consumer_emits_transcripts(event_bus, mock_audio_frame):
    """Test STTConsumer processes audio and emits transcript events."""
    stt_queue = asyncio.Queue()
    
    mock_stt = AsyncMock()
    
    async def mock_recognize_stream(audio_gen):
        async for _ in audio_gen:
            yield TranscriptSegment(
                text="hello world",
                is_final=True,
                confidence=0.95,
            )
            break
    
    mock_stt.recognize_stream = mock_recognize_stream
    
    consumer = STTConsumer(
        event_bus,
        mock_stt,
        stt_queue,
    )
    
    await stt_queue.put(mock_audio_frame)
    
    task = asyncio.create_task(consumer.run())
    
    await asyncio.sleep(0.1)
    
    consumer.close()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    
    event = await event_bus.get()
    assert event.type == EventType.STT_FINAL_TRANSCRIPT
    assert event.data.segment.text == "hello world"


@pytest.mark.asyncio
async def test_audio_turn_consumer_emits_probability(event_bus, mock_audio_frame):
    """Test AudioTurnConsumer processes audio and emits turn probability."""
    audio_turn_queue = asyncio.Queue()
    
    mock_detector = AsyncMock()
    mock_detector.process_audio.return_value = 0.75
    
    consumer = AudioTurnConsumer(
        event_bus,
        mock_detector,
        audio_turn_queue,
    )
    
    await audio_turn_queue.put((mock_audio_frame, 0.9))
    
    task = asyncio.create_task(consumer.run())
    
    await asyncio.sleep(0.1)
    
    consumer.close()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    
    event = await event_bus.get()
    assert event.type == EventType.AUDIO_TURN_PROBABILITY
    assert event.data.probability == 0.75
    assert event.data.source == "audio"


@pytest.mark.asyncio
async def test_zero_copy_audio_frames(event_bus, mock_audio_frame):
    """Test that the same AudioFrame object is passed to all consumers."""
    vad_queue = asyncio.Queue()
    stt_queue = asyncio.Queue()
    audio_turn_queue = asyncio.Queue()
    
    mock_pipeline = AsyncMock()
    
    async def mock_input_stream():
        yield mock_audio_frame
    
    mock_pipeline.input_stream = mock_input_stream
    
    mock_vad = AsyncMock()
    mock_vad.process_audio.return_value = VADSignal(
        is_speech=True,
        probability=0.8,
        timestamp=0.0,
    )
    
    distributor = AudioDistributor(
        event_bus,
        mock_pipeline,
        vad_queue,
        stt_queue,
    )
    
    vad_consumer = VADConsumer(
        event_bus,
        mock_vad,
        vad_queue,
        audio_turn_queue=audio_turn_queue,
    )
    
    dist_task = asyncio.create_task(distributor.run())
    vad_task = asyncio.create_task(vad_consumer.run())
    
    await asyncio.sleep(0.1)
    
    distributor.close()
    vad_consumer.close()
    
    dist_task.cancel()
    vad_task.cancel()
    
    try:
        await dist_task
    except asyncio.CancelledError:
        pass
    
    try:
        await vad_task
    except asyncio.CancelledError:
        pass
    
    stt_frame = await stt_queue.get()
    turn_frame, _ = await audio_turn_queue.get()
    
    assert stt_frame is mock_audio_frame
    assert turn_frame is mock_audio_frame
