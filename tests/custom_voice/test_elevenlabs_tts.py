"""Tests for ElevenLabsTTS (persistent WebSocket / HTTP implementation)."""

from __future__ import annotations

import asyncio
import base64
import json
import struct
from collections.abc import AsyncIterable
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from livekit import rtc

from custom_voice.tts.cartesia import ChunkingStrategy
from custom_voice.tts.elevenlabs import ElevenLabsTTS, ElevenLabsTTSWrapper


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pcm_bytes(samples: int = 441) -> bytes:
    """Return `samples` zero-valued 16-bit PCM samples as bytes."""
    return struct.pack(f"<{samples}h", *([0] * samples))


def _b64_pcm(samples: int = 441) -> str:
    return base64.b64encode(_pcm_bytes(samples)).decode()


def _ws_text_msg(audio_b64: str | None = None, is_final: bool = False) -> MagicMock:
    """Build a fake aiohttp WebSocket TEXT message."""
    import aiohttp
    payload: dict = {}
    if audio_b64:
        payload["audio"] = audio_b64
    if is_final:
        payload["isFinal"] = True
    msg = MagicMock()
    msg.type = aiohttp.WSMsgType.TEXT
    msg.data = json.dumps(payload)
    return msg


def _ws_close_msg() -> MagicMock:
    import aiohttp
    msg = MagicMock()
    msg.type = aiohttp.WSMsgType.CLOSED
    return msg


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

def test_initialization_defaults():
    tts = ElevenLabsTTS(voice_id="v", api_key="k")
    assert tts.model == "eleven_turbo_v2_5"
    assert tts.voice == "v"
    assert tts.sample_rate == 22050
    assert tts._output_format == "pcm_22050"


def test_initialization_custom_sample_rate():
    tts = ElevenLabsTTS(voice_id="v", api_key="k", sample_rate=16000)
    assert tts._output_format == "pcm_16000"


def test_unsupported_sample_rate():
    with pytest.raises(ValueError, match="Unsupported sample rate"):
        ElevenLabsTTS(voice_id="v", api_key="k", sample_rate=8000)


def test_requires_api_key():
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ValueError, match="API key is required"):
            ElevenLabsTTS(voice_id="v")


def test_api_key_from_env():
    with patch.dict("os.environ", {"ELEVEN_API_KEY": "env-key"}):
        tts = ElevenLabsTTS(voice_id="v")
        assert tts._api_key == "env-key"


def test_alias():
    assert ElevenLabsTTSWrapper is ElevenLabsTTS


# ---------------------------------------------------------------------------
# Per-utterance WebSocket: synthesize_stream with mocked WS
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_synthesize_websocket_string():
    """synthesize_stream opens WS, sends text + EOS, yields frames."""
    tts = ElevenLabsTTS(voice_id="v", api_key="k", transport="websocket")

    # Mock WebSocket that returns audio frames
    frame_data = _pcm_bytes(441)
    
    async def mock_ws_messages():
        # Yield audio message
        yield MagicMock(
            type=aiohttp.WSMsgType.TEXT,
            data=json.dumps({
                "audio": base64.b64encode(frame_data).decode(),
            })
        )
        # Yield isFinal message
        yield MagicMock(
            type=aiohttp.WSMsgType.TEXT,
            data=json.dumps({"isFinal": True})
        )
    
    mock_ws = AsyncMock()
    mock_ws.closed = False
    mock_ws.send_json = AsyncMock()
    mock_ws.__aiter__ = lambda self: mock_ws_messages()
    mock_ws.close = AsyncMock()

    with patch.object(tts, "_get_session") as mock_get:
        mock_session = AsyncMock()
        mock_session.ws_connect = AsyncMock(return_value=mock_ws)
        mock_get.return_value = mock_session

        frames = []
        async for f in tts.synthesize_stream("Hello world"):
            frames.append(f)

        assert len(frames) == 1
        # Verify text and EOS were sent
        assert mock_ws.send_json.call_count == 2
        first_call = mock_ws.send_json.call_args_list[0][0][0]
        assert first_call["text"] == "Hello world "
        last_call = mock_ws.send_json.call_args_list[1][0][0]
        assert last_call == {"text": ""}


@pytest.mark.asyncio
async def test_synthesize_websocket_opens_per_utterance():
    """Each synthesize_stream call opens a new WebSocket connection."""
    tts = ElevenLabsTTS(voice_id="v", api_key="k", transport="websocket")

    frame_data = _pcm_bytes(441)
    
    async def mock_ws_messages():
        yield MagicMock(
            type=aiohttp.WSMsgType.TEXT,
            data=json.dumps({
                "audio": base64.b64encode(frame_data).decode(),
                "isFinal": True,
            })
        )
    
    mock_ws = AsyncMock()
    mock_ws.closed = False
    mock_ws.send_json = AsyncMock()
    mock_ws.__aiter__ = lambda self: mock_ws_messages()
    mock_ws.close = AsyncMock()

    with patch.object(tts, "_get_session") as mock_get:
        mock_session = AsyncMock()
        mock_session.ws_connect = AsyncMock(return_value=mock_ws)
        mock_get.return_value = mock_session

        # First call
        async for _ in tts.synthesize_stream("test 1"):
            pass
        
        # Second call should open a NEW WebSocket
        async for _ in tts.synthesize_stream("test 2"):
            pass

        # Should have opened 2 separate connections
        assert mock_session.ws_connect.call_count == 2


# ---------------------------------------------------------------------------
# HTTP transport
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_synthesize_http():
    """synthesize_stream with HTTP transport yields frames from PCM response."""
    samples = int(22050 * 0.02)  # 20 ms = 441 samples
    raw_pcm = _pcm_bytes(samples)

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()

    async def iter_chunked(_size):
        yield raw_pcm

    mock_response.content.iter_chunked = iter_chunked
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=mock_response)

    tts = ElevenLabsTTS(
        voice_id="v", api_key="k", transport="http", sample_rate=22050
    )
    tts._session = mock_session

    frames = [f async for f in tts.synthesize_stream("Hello")]
    assert len(frames) >= 1
    assert frames[0].sample_rate == 22050


# ---------------------------------------------------------------------------
# synthesize_stream_from_iterator chunking
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sentence_chunking():
    """SENTENCE strategy flushes at punctuation."""
    tts = ElevenLabsTTS(
        voice_id="v", api_key="k",
        chunking_strategy=ChunkingStrategy.SENTENCE,
        min_chunk_size=5,
    )

    call_count = 0

    async def patched(text: str | AsyncIterable[str]) -> AsyncIterable[rtc.AudioFrame]:
        nonlocal call_count
        call_count += 1
        yield rtc.AudioFrame(
            data=_pcm_bytes(441), sample_rate=22050, num_channels=1, samples_per_channel=441
        )

    tts.synthesize_stream = patched  # type: ignore[method-assign]

    async def tokens():
        for t in ["Hello", ".", " ", "World", "."]:
            yield t

    frames = [f async for f in tts.synthesize_stream_from_iterator(tokens())]
    assert call_count == 2
    assert len(frames) == 2


@pytest.mark.asyncio
async def test_word_chunking():
    """WORD strategy flushes at word boundaries."""
    tts = ElevenLabsTTS(
        voice_id="v", api_key="k",
        chunking_strategy=ChunkingStrategy.WORD,
        min_chunk_size=5,
    )

    call_count = 0

    async def patched(text: str | AsyncIterable[str]) -> AsyncIterable[rtc.AudioFrame]:
        nonlocal call_count
        call_count += 1
        yield rtc.AudioFrame(
            data=_pcm_bytes(441), sample_rate=22050, num_channels=1, samples_per_channel=441
        )

    tts.synthesize_stream = patched  # type: ignore[method-assign]

    async def tokens():
        for t in ["Hello", " ", "World"]:
            yield t

    [f async for f in tts.synthesize_stream_from_iterator(tokens())]
    assert call_count == 2


# ---------------------------------------------------------------------------
# close()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_close_cleans_up():
    """close() closes the aiohttp session."""
    tts = ElevenLabsTTS(voice_id="v", api_key="k")

    mock_session = AsyncMock()
    tts._session = mock_session

    await tts.close()

    mock_session.close.assert_called_once()
    assert tts._closed is True


@pytest.mark.asyncio
async def test_close_no_session():
    """close() is safe when no session was ever created."""
    tts = ElevenLabsTTS(voice_id="v", api_key="k")
    await tts.close()
    assert tts._closed is True
