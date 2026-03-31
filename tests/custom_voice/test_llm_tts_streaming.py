"""Integration tests for LLM→TTS streaming pipeline."""

import asyncio
from collections.abc import AsyncIterable

import numpy as np
import pytest
from livekit import rtc

from custom_voice.tts.cartesia import CartesiaTTS, ChunkingStrategy


class MockLLM:
    """Mock LLM that yields tokens."""
    
    def __init__(self, tokens: list[str]):
        self._tokens = tokens
    
    async def generate_stream(self, messages) -> AsyncIterable[str]:
        """Yield tokens one at a time."""
        for token in self._tokens:
            await asyncio.sleep(0.01)
            yield token


class MockCartesiaTTS(CartesiaTTS):
    """Mock Cartesia TTS for testing without API calls."""
    
    def __init__(self, **kwargs):
        kwargs.setdefault('voice', 'test-voice')
        kwargs.setdefault('api_key', 'test-key')
        super().__init__(**kwargs)
        self._synthesized_chunks = []
    
    async def synthesize_stream(self, text: str | AsyncIterable[str]) -> AsyncIterable[rtc.AudioFrame]:
        """Mock synthesis - just records what was sent."""
        if isinstance(text, str):
            full_text = text
        else:
            chunks = []
            async for chunk in text:
                chunks.append(chunk)
            full_text = "".join(chunks)
        
        self._synthesized_chunks.append(full_text)
        
        audio_data = np.zeros(480, dtype=np.int16)
        frame = rtc.AudioFrame(
            data=audio_data.tobytes(),
            sample_rate=24000,
            num_channels=1,
            samples_per_channel=480,
        )
        yield frame


@pytest.mark.asyncio
async def test_sentence_chunking_strategy():
    """Test that SENTENCE strategy buffers until punctuation."""
    tts = MockCartesiaTTS(
        chunking_strategy=ChunkingStrategy.SENTENCE,
        min_chunk_size=5,
    )
    
    tokens = ["Hello", " ", "world", ".", " ", "How", " ", "are", " ", "you", "?"]
    
    async def token_stream():
        for token in tokens:
            yield token
    
    frames = []
    async for frame in tts.synthesize_stream_from_iterator(token_stream()):
        frames.append(frame)
    
    assert len(frames) == 2
    assert len(tts._synthesized_chunks) == 2
    assert tts._synthesized_chunks[0] == "Hello world."
    assert tts._synthesized_chunks[1] == "How are you?"


@pytest.mark.asyncio
async def test_word_chunking_strategy():
    """Test that WORD strategy buffers until word boundary."""
    tts = MockCartesiaTTS(
        chunking_strategy=ChunkingStrategy.WORD,
        min_chunk_size=5,
    )
    
    tokens = ["Hello", " ", "world", " ", "test"]
    
    async def token_stream():
        for token in tokens:
            yield token
    
    frames = []
    async for frame in tts.synthesize_stream_from_iterator(token_stream()):
        frames.append(frame)
    
    assert len(frames) >= 2
    assert tts._synthesized_chunks[0] == "Hello"
    assert "world" in tts._synthesized_chunks[1]


@pytest.mark.asyncio
async def test_immediate_chunking_strategy():
    """Test that IMMEDIATE strategy sends as soon as min_chunk_size reached."""
    tts = MockCartesiaTTS(
        chunking_strategy=ChunkingStrategy.IMMEDIATE,
        min_chunk_size=5,
    )
    
    tokens = ["Hello", "World", "Test"]
    
    async def token_stream():
        for token in tokens:
            yield token
    
    frames = []
    async for frame in tts.synthesize_stream_from_iterator(token_stream()):
        frames.append(frame)
    
    assert len(frames) >= 2


@pytest.mark.asyncio
async def test_llm_tts_pipeline_integration():
    """Test full LLM→TTS streaming pipeline."""
    llm = MockLLM(["Hello", " ", "world", ".", " ", "This", " ", "is", " ", "a", " ", "test", "."])
    
    tts = MockCartesiaTTS(
        chunking_strategy=ChunkingStrategy.SENTENCE,
        min_chunk_size=5,
    )
    
    token_stream = llm.generate_stream([])
    
    frames = []
    async for frame in tts.synthesize_stream_from_iterator(token_stream):
        frames.append(frame)
    
    assert len(frames) == 2
    assert tts._synthesized_chunks[0] == "Hello world."
    assert tts._synthesized_chunks[1] == "This is a test."


@pytest.mark.asyncio
async def test_chunking_respects_min_chunk_size():
    """Test that chunks are not sent until min_chunk_size is reached."""
    tts = MockCartesiaTTS(
        chunking_strategy=ChunkingStrategy.SENTENCE,
        min_chunk_size=20,
    )
    
    tokens = ["Hi", "."]
    
    async def token_stream():
        for token in tokens:
            yield token
    
    frames = []
    async for frame in tts.synthesize_stream_from_iterator(token_stream()):
        frames.append(frame)
    
    assert len(frames) == 1
    assert tts._synthesized_chunks[0] == "Hi."


@pytest.mark.asyncio
async def test_cancellation_during_streaming():
    """Test that streaming can be cancelled mid-generation."""
    tts = MockCartesiaTTS(
        chunking_strategy=ChunkingStrategy.SENTENCE,
        min_chunk_size=5,
    )
    
    async def slow_token_stream():
        for i in range(100):
            await asyncio.sleep(0.1)
            yield f"word{i} "
            if i % 10 == 0:
                yield ". "
    
    frames = []
    
    async def collect_frames():
        async for frame in tts.synthesize_stream_from_iterator(slow_token_stream()):
            frames.append(frame)
    
    task = asyncio.create_task(collect_frames())
    
    await asyncio.sleep(0.3)
    
    task.cancel()
    
    try:
        await task
    except asyncio.CancelledError:
        pass
    
    assert len(frames) < 10
