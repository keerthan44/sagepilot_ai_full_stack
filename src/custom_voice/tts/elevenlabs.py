"""ElevenLabs TTS - direct HTTP/WebSocket implementation.

WebSocket transport: opens a new connection for each utterance (ElevenLabs
closes the connection after each complete synthesis). Each call to
synthesize_stream() opens a WebSocket, sends text, reads audio frames,
and closes the connection.

HTTP transport: stateless POST → chunked PCM response, no persistent state.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
from collections.abc import AsyncIterable
from typing import Any, Literal

import aiohttp
from livekit import rtc

from .base import BaseTTS
from .cartesia import ChunkingStrategy

logger = logging.getLogger("custom-agent")

_BASE_URL = "https://api.elevenlabs.io/v1"

# ElevenLabs PCM output formats keyed by sample rate
_PCM_FORMAT: dict[int, str] = {
    16000: "pcm_16000",
    22050: "pcm_22050",
    24000: "pcm_24000",
    44100: "pcm_44100",
}


class ElevenLabsTTS(BaseTTS):
    """
    ElevenLabs Text-to-Speech implementation.

    WebSocket transport:
        Opens a new WebSocket connection for each utterance. ElevenLabs closes
        the connection after synthesis completes, so connections cannot be reused.

    HTTP transport:
        Stateless streaming POST per utterance — recommended for reliability.
    """

    def __init__(
        self,
        *,
        model: str = "eleven_turbo_v2_5",
        voice_id: str = "l7kNoIfnJKPg7779LI2t",
        transport: Literal["websocket", "http"] = "websocket",
        api_key: str | None = None,
        base_url: str = _BASE_URL,
        sample_rate: int = 22050,
        stability: float = 0.5,
        similarity_boost: float = 0.75,
        style: float = 0.0,
        use_speaker_boost: bool = True,
        chunking_strategy: ChunkingStrategy = ChunkingStrategy.SENTENCE,
        min_chunk_size: int = 10,
        **kwargs: Any,
    ):
        """
        Initialize ElevenLabs TTS.

        Args:
            model: ElevenLabs model (e.g., "eleven_turbo_v2_5", "eleven_multilingual_v2")
            voice_id: ElevenLabs voice ID
            transport: Transport protocol ("websocket" or "http")
            api_key: ElevenLabs API key (or set ELEVEN_API_KEY env var)
            base_url: Base API URL
            sample_rate: Audio sample rate in Hz (16000, 22050, 24000, or 44100)
            stability: Voice stability [0.0 - 1.0]
            similarity_boost: Voice similarity boost [0.0 - 1.0]
            style: Style exaggeration [0.0 - 1.0]
            use_speaker_boost: Whether to use speaker boost
            chunking_strategy: Text chunking strategy for streaming (sentence, word, immediate)
            min_chunk_size: Minimum characters before flushing a chunk
        """
        if sample_rate not in _PCM_FORMAT:
            raise ValueError(
                f"Unsupported sample rate {sample_rate}. "
                f"Supported: {sorted(_PCM_FORMAT.keys())}"
            )

        super().__init__(model=model, voice=voice_id, sample_rate=sample_rate)

        self._api_key = api_key or os.environ.get("ELEVEN_API_KEY")
        if not self._api_key:
            raise ValueError(
                "ElevenLabs API key is required. Set ELEVEN_API_KEY environment "
                "variable or pass api_key parameter."
            )

        self._voice_id = voice_id
        self._transport = transport
        self._base_url = base_url.rstrip("/")
        self._output_format = _PCM_FORMAT[sample_rate]
        self._stability = stability
        self._similarity_boost = similarity_boost
        self._style = style
        self._use_speaker_boost = use_speaker_boost
        self._chunking_strategy = chunking_strategy
        self._min_chunk_size = min_chunk_size

        # aiohttp session (shared between HTTP and WS)
        self._session: aiohttp.ClientSession | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_session(self) -> aiohttp.ClientSession:
        """Get or create the shared aiohttp session."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session

    def _voice_settings(self) -> dict[str, Any]:
        return {
            "stability": self._stability,
            "similarity_boost": self._similarity_boost,
            "style": self._style,
            "use_speaker_boost": self._use_speaker_boost,
        }

    def _pcm_to_frame(self, raw: bytes) -> rtc.AudioFrame | None:
        """Convert raw 16-bit signed PCM bytes to an rtc.AudioFrame."""
        n = len(raw) // 2
        if n == 0:
            return None
        return rtc.AudioFrame(
            data=raw[: n * 2],
            sample_rate=self._sample_rate,
            num_channels=1,
            samples_per_channel=n,
        )

    def _ws_url(self) -> str:
        ws_base = (
            self._base_url
            .replace("https://", "wss://")
            .replace("http://", "ws://")
        )
        return (
            f"{ws_base}/text-to-speech/{self._voice_id}/stream-input"
            f"?model_id={self._model}&output_format={self._output_format}"
            f"&optimize_streaming_latency=4"
        )


    # ------------------------------------------------------------------
    # Transport implementations
    # ------------------------------------------------------------------

    async def _synthesize_websocket(
        self,
        text: str | AsyncIterable[str],
    ) -> AsyncIterable[rtc.AudioFrame]:
        """
        Synthesize via WebSocket (per-utterance connection).
        
        Note: ElevenLabs closes the WebSocket after each utterance completes,
        so we open a new connection for each synthesis call.
        """
        # Open a fresh WebSocket for this utterance
        session = self._get_session()
        logger.debug("ElevenLabsTTS: opening WebSocket for utterance")
        
        ws = await session.ws_connect(
            self._ws_url(),
            headers={"xi-api-key": self._api_key},
        )
        
        # Create a local queue for this utterance
        utterance_queue: asyncio.Queue[rtc.AudioFrame | None] = asyncio.Queue()
        
        # Start reader task for this utterance
        async def reader() -> None:
            frames_read = 0
            messages_read = 0
            try:
                async for msg in ws:
                    messages_read += 1
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        if messages_read == 1:
                            logger.debug("ElevenLabsTTS: WS first message: %s", json.dumps(data)[:200])

                        audio_b64 = data.get("audio", "")
                        if audio_b64:
                            audio_bytes = base64.b64decode(audio_b64)
                            frame = self._pcm_to_frame(audio_bytes)
                            if frame:
                                frames_read += 1
                                if frames_read == 1:
                                    logger.info("ElevenLabsTTS: WS first audio frame (%d samples)", frame.samples_per_channel)
                                await utterance_queue.put(frame)

                        if data.get("isFinal"):
                            logger.debug("ElevenLabsTTS: WS received isFinal (%d frames)", frames_read)
                            await utterance_queue.put(None)
                            break

                    elif msg.type == aiohttp.WSMsgType.BINARY:
                        frame = self._pcm_to_frame(msg.data)
                        if frame:
                            frames_read += 1
                            await utterance_queue.put(frame)

                    elif msg.type in (
                        aiohttp.WSMsgType.CLOSED,
                        aiohttp.WSMsgType.CLOSE,
                        aiohttp.WSMsgType.CLOSING,
                        aiohttp.WSMsgType.ERROR,
                    ):
                        logger.debug("ElevenLabsTTS: WS closed by server (type=%s)", msg.type)
                        break

            except asyncio.CancelledError:
                logger.debug("ElevenLabsTTS: WS reader cancelled")
            except Exception:
                logger.exception("ElevenLabsTTS: WS reader error")
            finally:
                await utterance_queue.put(None)
                logger.debug("ElevenLabsTTS: WS reader done (%d messages, %d frames)", messages_read, frames_read)
        
        reader_task = asyncio.create_task(reader())
        
        try:
            # ---- Send text to ElevenLabs ----
            if isinstance(text, str):
                logger.debug("ElevenLabsTTS: WS sending text chunk: %r", text[:80])
                await ws.send_json({
                    "text": text + " ",
                    "voice_settings": self._voice_settings(),
                })
                logger.debug("ElevenLabsTTS: WS sending EOS signal")
                await ws.send_json({"text": ""})
            else:
                # Streaming tokens from LLM
                logger.debug("ElevenLabsTTS: WS streaming tokens from iterator")
                first = True
                token_count = 0
                async for token in text:
                    token_count += 1
                    if token_count == 1:
                        logger.debug("ElevenLabsTTS: WS first streamed token: %r", token[:20])
                    
                    if self._check_cancelled():
                        reader_task.cancel()
                        try:
                            await reader_task
                        except asyncio.CancelledError:
                            pass
                        return
                    msg: dict[str, Any] = {"text": token}
                    if first:
                        msg["voice_settings"] = self._voice_settings()
                        first = False
                    await ws.send_json(msg)
                
                logger.debug("ElevenLabsTTS: WS sent %d tokens, sending EOS", token_count)
                await ws.send_json({"text": ""})

            # ---- Read audio frames until end-of-utterance ----
            frames_yielded = 0
            while True:
                frame = await utterance_queue.get()
                if frame is None:
                    break

                if self._check_cancelled():
                    # Drain remaining frames
                    while not utterance_queue.empty():
                        try:
                            utterance_queue.get_nowait()
                        except asyncio.QueueEmpty:
                            break
                    return

                frames_yielded += 1
                yield frame

            logger.debug("ElevenLabsTTS: utterance complete (%d frames)", frames_yielded)
        
        finally:
            # Clean up
            reader_task.cancel()
            try:
                await reader_task
            except asyncio.CancelledError:
                pass
            
            if not ws.closed:
                await ws.close()
            
            logger.debug("ElevenLabsTTS: WebSocket closed for utterance")


    async def _synthesize_http(
        self,
        text: str | AsyncIterable[str],
    ) -> AsyncIterable[rtc.AudioFrame]:
        """Synthesize via HTTP streaming (POST → chunked PCM response)."""
        if isinstance(text, str):
            full_text = text
        else:
            parts: list[str] = []
            async for token in text:
                if self._check_cancelled():
                    return
                parts.append(token)
            full_text = "".join(parts)

        if not full_text:
            return

        logger.debug("ElevenLabsTTS: HTTP synthesis: %r", full_text[:80])

        url = f"{self._base_url}/text-to-speech/{self._voice_id}/stream"
        params = {"output_format": self._output_format, "model_id": self._model}
        payload = {
            "text": full_text,
            "model_id": self._model,
            "voice_settings": self._voice_settings(),
        }

        session = self._get_session()
        frames_yielded = 0
        buf = b""
        # Emit fixed-size 20 ms frames
        frame_bytes = int(self._sample_rate * 0.02) * 2  # 16-bit samples

        async with session.post(
            url,
            params=params,
            json=payload,
            headers={
                "xi-api-key": self._api_key,
                "Accept": "audio/pcm",
            },
        ) as response:
            if response.status != 200:
                body = await response.text()
                logger.error(
                    "ElevenLabsTTS: HTTP error %d: %s", response.status, body[:200]
                )
                response.raise_for_status()

            logger.info(
                "ElevenLabsTTS: HTTP streaming started (format=%s)", self._output_format
            )
            chunks_received = 0
            async for chunk in response.content.iter_chunked(4096):
                if self._check_cancelled():
                    return
                chunks_received += 1
                if chunks_received == 1:
                    logger.debug("ElevenLabsTTS: first HTTP chunk received (%d bytes)", len(chunk))
                buf += chunk

                while len(buf) >= frame_bytes:
                    frame = self._pcm_to_frame(buf[:frame_bytes])
                    buf = buf[frame_bytes:]
                    if frame:
                        frames_yielded += 1
                        if frames_yielded == 1:
                            logger.info("ElevenLabsTTS: first audio frame yielded")
                        yield frame

            # Flush remainder
            if buf and not self._check_cancelled():
                frame = self._pcm_to_frame(buf)
                if frame:
                    frames_yielded += 1
                    yield frame

        logger.info(
            "ElevenLabsTTS: HTTP synthesis done (%d chunks received, %d frames, ~%d ms)",
            chunks_received,
            frames_yielded,
            frames_yielded * 20,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def synthesize_stream(
        self,
        text: str | AsyncIterable[str],
    ) -> AsyncIterable[rtc.AudioFrame]:
        """
        Synthesize speech with streaming output.

        WebSocket transport: reuses the persistent connection — no handshake
        overhead after the first call.

        Args:
            text: Text to synthesize (string or async iterable of tokens)

        Yields:
            Audio frames as they arrive
        """
        self._check_closed()
        self._reset_cancel()

        if self._transport == "websocket":
            async for frame in self._synthesize_websocket(text):
                if self._check_cancelled():
                    break
                yield frame
        else:
            async for frame in self._synthesize_http(text):
                if self._check_cancelled():
                    break
                yield frame

    async def synthesize_stream_from_iterator(
        self,
        text_iterator: AsyncIterable[str],
    ) -> AsyncIterable[rtc.AudioFrame]:
        """
        Synthesize audio from a streaming LLM token iterator with internal chunking.

        Buffers tokens and flushes based on the configured strategy:
        - SENTENCE: flush at sentence-ending punctuation (. ! ? \\n)
        - WORD: flush at word boundaries (space)
        - IMMEDIATE: flush as soon as min_chunk_size chars are buffered

        Args:
            text_iterator: Async iterator yielding text tokens from the LLM

        Yields:
            Audio frames as they are synthesized
        """
        self._check_closed()
        self._reset_cancel()
        
        buffer = ""
        sentence_endings = ('.', '!', '?', '\n')
        chunks_sent = 0
        audio_frames_yielded = 0
        logger.debug(
            "ElevenLabsTTS: starting streaming synthesis (strategy=%s)",
            self._chunking_strategy.value,
        )

        token_count = 0
        try:
            async for token in text_iterator:
                token_count += 1
                if token_count == 1:
                    logger.debug("ElevenLabsTTS: first token received from LLM: %r", token[:20])
                elif token_count % 20 == 0:
                    logger.debug("ElevenLabsTTS: received %d tokens so far", token_count)
                
                if self._check_cancelled():
                    logger.debug("ElevenLabsTTS: cancelled after %d tokens", token_count)
                    break

                buffer += token
                should_flush = False

                if self._chunking_strategy == ChunkingStrategy.IMMEDIATE:
                    should_flush = len(buffer) >= self._min_chunk_size

                elif self._chunking_strategy == ChunkingStrategy.SENTENCE:
                    should_flush = (
                        bool(buffer)
                        and buffer[-1] in sentence_endings
                        and len(buffer) >= self._min_chunk_size
                    )

                elif self._chunking_strategy == ChunkingStrategy.WORD:
                    should_flush = (
                        buffer.endswith(' ')
                        and len(buffer) >= self._min_chunk_size
                    )

                if should_flush:
                    chunk = buffer.strip()
                    if chunk:
                        chunks_sent += 1
                        logger.debug(
                            "ElevenLabsTTS: flushing chunk %d (%d chars): %r",
                            chunks_sent,
                            len(chunk),
                            chunk[:60],
                        )
                        async for audio_frame in self.synthesize_stream(chunk):
                            if self._check_cancelled():
                                return
                            audio_frames_yielded += 1
                            yield audio_frame
                    buffer = ""
                else:
                    if token_count <= 5 or token_count % 50 == 0:
                        logger.debug(
                            "ElevenLabsTTS: buffering token %d (buffer_size=%d, should_flush=%s)",
                            token_count,
                            len(buffer),
                            should_flush,
                        )
        except Exception:
            logger.exception("ElevenLabsTTS: error while consuming token iterator")
            raise

        logger.debug("ElevenLabsTTS: finished consuming tokens (total=%d, buffer_remaining=%d)", token_count, len(buffer))
        
        if buffer.strip() and not self._check_cancelled():
            chunks_sent += 1
            logger.debug(
                "ElevenLabsTTS: synthesizing final chunk %d: %r",
                chunks_sent,
                buffer.strip()[:60],
            )
            async for audio_frame in self.synthesize_stream(buffer.strip()):
                if self._check_cancelled():
                    return
                audio_frames_yielded += 1
                yield audio_frame

        logger.info(
            "ElevenLabsTTS: streaming synthesis complete (%d tokens, %d chunks, %d audio frames)",
            token_count,
            chunks_sent,
            audio_frames_yielded,
        )

    async def synthesize(self, text: str) -> list[rtc.AudioFrame]:
        """
        Synthesize complete speech from text.

        Args:
            text: Text to synthesize

        Returns:
            List of audio frames
        """
        frames = []
        async for frame in self.synthesize_stream(text):
            frames.append(frame)
        return frames

    async def close(self) -> None:
        """Close the aiohttp session."""
        await super().close()

        # Close aiohttp session
        if self._session is not None:
            await self._session.close()
            self._session = None


# Backwards-compat alias
ElevenLabsTTSWrapper = ElevenLabsTTS
