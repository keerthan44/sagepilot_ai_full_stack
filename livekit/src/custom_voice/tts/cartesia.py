"""Cartesia TTS implementation (placeholder/simplified)."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
from collections.abc import AsyncIterable
from enum import Enum
from typing import Any, Literal

import aiohttp
import numpy as np
from livekit import rtc

from .base import BaseTTS

logger = logging.getLogger("custom-agent")


class ChunkingStrategy(Enum):
    """Text chunking strategies for streaming TTS."""
    SENTENCE = "sentence"
    WORD = "word"
    IMMEDIATE = "immediate"


class CartesiaTTS(BaseTTS):
    """
    Cartesia Text-to-Speech implementation.
    
    NOTE: This is a simplified implementation. The actual Cartesia SDK
    may have different APIs. Adjust based on actual Cartesia documentation.
    
    Supports both WebSocket (streaming) and HTTP (batch) transports.
    """
    
    def __init__(
        self,
        *,
        model: str = "sonic-3",
        voice: str,
        transport: Literal["websocket", "http"] = "websocket",
        api_key: str | None = None,
        base_url: str = "https://api.cartesia.ai",
        api_version: str = "2024-06-10",
        sample_rate: int = 24000,
        chunking_strategy: ChunkingStrategy = ChunkingStrategy.SENTENCE,
        min_chunk_size: int = 10,
        **kwargs: Any,
    ):
        """
        Initialize Cartesia TTS.
        
        Args:
            model: Cartesia model (e.g., "sonic-3")
            voice: Voice ID
            transport: Transport protocol ("websocket" or "http")
            api_key: Cartesia API key (or set CARTESIA_API_KEY env var)
            base_url: Base API URL (default: https://api.cartesia.ai)
            api_version: Cartesia API version (default: 2024-06-10)
            sample_rate: Audio sample rate in Hz
            chunking_strategy: Strategy for chunking streaming text (sentence, word, immediate)
            min_chunk_size: Minimum characters before sending chunk to synthesis
            **kwargs: Additional parameters
        """
        super().__init__(
            model=model,
            voice=voice,
            sample_rate=sample_rate,
        )
        
        # Get API key
        self._api_key = api_key or os.environ.get("CARTESIA_API_KEY")
        if not self._api_key:
            raise ValueError(
                "Cartesia API key is required. Set CARTESIA_API_KEY environment "
                "variable or pass api_key parameter."
            )
        
        self._transport = transport
        self._base_url = base_url
        self._api_version = api_version
        self._chunking_strategy = chunking_strategy
        self._min_chunk_size = min_chunk_size
        self._session: aiohttp.ClientSession | None = None
    
    def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def synthesize_stream(
        self,
        text: str | AsyncIterable[str],
    ) -> AsyncIterable[rtc.AudioFrame]:
        """
        Synthesize speech with streaming output.
        
        Args:
            text: Text to synthesize (string or async iterable)
            
        Yields:
            Audio frames as they are synthesized
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
    
    async def _synthesize_websocket(
        self,
        text: str | AsyncIterable[str],
    ) -> AsyncIterable[rtc.AudioFrame]:
        """Synthesize using WebSocket transport."""
        session = self._get_session()
        
        # Build WebSocket URL with API key and version as query parameters
        ws_base = self._base_url.replace("https://", "wss://").replace("http://", "ws://")
        ws_url = f"{ws_base}/tts/websocket?api_key={self._api_key}&cartesia_version={self._api_version}"
        
        logger.debug("CartesiaTTS: connecting to WebSocket (url=%s)", ws_url.replace(self._api_key, "***"))
        
        async with session.ws_connect(
            ws_url,
            headers={"User-Agent": "CartesiaTTS/1.0 (integration=CustomVoiceStack)"},
        ) as ws:
            logger.info("CartesiaTTS: WebSocket connected")
            
            # Task to send text
            async def send_text():
                try:
                    # Build base message with voice and output format
                    base_msg = {
                        "model_id": self._model,
                        "voice": {
                            "mode": "id",
                            "id": self._voice,
                        },
                        "output_format": {
                            "container": "raw",
                            "encoding": "pcm_s16le",
                            "sample_rate": self._sample_rate,
                        },
                        "language": "en",
                    }
                    
                    if isinstance(text, str):
                        # Single text message
                        msg = base_msg.copy()
                        msg["transcript"] = text
                        msg["continue"] = False
                        await ws.send_str(json.dumps(msg))
                        logger.debug("CartesiaTTS: sent single text chunk: %r", text[:50])
                    else:
                        # Streaming text chunks
                        chunk_count = 0
                        async for chunk in text:
                            if self._check_cancelled():
                                break
                            
                            chunk_count += 1
                            msg = base_msg.copy()
                            msg["transcript"] = chunk
                            msg["continue"] = True  # More chunks coming
                            await ws.send_str(json.dumps(msg))
                            logger.debug("CartesiaTTS: sent text chunk %d: %r", chunk_count, chunk[:50])
                        
                        # Send final empty chunk to signal end
                        if not self._check_cancelled():
                            end_msg = base_msg.copy()
                            end_msg["transcript"] = " "
                            end_msg["continue"] = False
                            await ws.send_str(json.dumps(end_msg))
                            logger.debug("CartesiaTTS: sent final chunk (continue=False)")
                except Exception:
                    logger.exception("CartesiaTTS: error in send_text task")
            
            # Start sending text
            send_task = asyncio.create_task(send_text())
            
            try:
                # Receive audio
                frame_count = 0
                async for msg in ws:
                    if self._check_cancelled():
                        logger.debug("CartesiaTTS: cancelled, stopping receive")
                        break
                    
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        
                        # Cartesia sends audio in "data" field as base64
                        if data.get("data"):
                            # Decode base64 audio
                            audio_b64 = data["data"]
                            audio_bytes = base64.b64decode(audio_b64)
                            
                            # Convert to audio frame
                            audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
                            frame = rtc.AudioFrame(
                                data=audio_array,
                                sample_rate=self._sample_rate,
                                num_channels=1,
                                samples_per_channel=len(audio_array),
                            )
                            frame_count += 1
                            if frame_count == 1:
                                logger.info("CartesiaTTS: first audio frame received (%d samples)", len(audio_array))
                            yield frame
                        
                        # Check for done signal
                        if data.get("done"):
                            logger.debug("CartesiaTTS: received done signal (%d frames)", frame_count)
                            break
                    
                    elif msg.type in (
                        aiohttp.WSMsgType.CLOSED,
                        aiohttp.WSMsgType.CLOSE,
                        aiohttp.WSMsgType.CLOSING,
                    ):
                        logger.debug("CartesiaTTS: WebSocket closed by server")
                        break
                    
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        logger.error("CartesiaTTS: WebSocket error")
                        break
            finally:
                send_task.cancel()
                try:
                    await send_task
                except asyncio.CancelledError:
                    pass
    
    async def _synthesize_http(
        self,
        text: str | AsyncIterable[str],
    ) -> AsyncIterable[rtc.AudioFrame]:
        """Synthesize using HTTP transport (bytes endpoint)."""
        # Collect text if it's a stream
        if isinstance(text, str):
            full_text = text
        else:
            chunks = []
            async for chunk in text:
                if self._check_cancelled():
                    return
                chunks.append(chunk)
            full_text = "".join(chunks)
        
        if not full_text:
            return
        
        session = self._get_session()
        
        # Build payload matching Cartesia's /tts/bytes endpoint
        payload = {
            "model_id": self._model,
            "transcript": full_text,
            "voice": {
                "mode": "id",
                "id": self._voice,
            },
            "output_format": {
                "container": "raw",
                "encoding": "pcm_s16le",
                "sample_rate": self._sample_rate,
            },
            "language": "en",
        }
        
        logger.debug("CartesiaTTS: HTTP request to /tts/bytes (text=%r)", full_text[:50])
        
        # Make HTTP request to /tts/bytes endpoint
        async with session.post(
            f"{self._base_url}/tts/bytes",
            json=payload,
            headers={
                "X-API-Key": self._api_key,
                "Cartesia-Version": self._api_version,
                "User-Agent": "CartesiaTTS/1.0 (integration=CustomVoiceStack)",
            },
        ) as response:
            response.raise_for_status()
            
            # Buffer for incomplete samples (PCM s16le = 2 bytes per sample)
            buffer = b""
            frame_count = 0
            
            # Stream audio chunks from response
            async for data, _ in response.content.iter_chunks():
                if self._check_cancelled():
                    break
                
                if not data:
                    continue
                
                # Add to buffer
                buffer += data
                
                # Process complete int16 samples (2 bytes each)
                # Keep any incomplete bytes in buffer
                bytes_per_sample = 2  # int16
                complete_bytes = (len(buffer) // bytes_per_sample) * bytes_per_sample
                
                if complete_bytes > 0:
                    # Extract complete samples
                    complete_data = buffer[:complete_bytes]
                    buffer = buffer[complete_bytes:]
                    
                    # Create audio frame directly from bytes (not numpy array)
                    num_samples = len(complete_data) // 2
                    frame = rtc.AudioFrame(
                        data=complete_data,
                        sample_rate=self._sample_rate,
                        num_channels=1,
                        samples_per_channel=num_samples,
                    )
                    frame_count += 1
                    if frame_count == 1:
                        logger.info("CartesiaTTS: first HTTP audio frame received (%d samples)", num_samples)
                    yield frame
            
            # Process any remaining buffered data
            if buffer and not self._check_cancelled():
                if len(buffer) % 2 == 0:  # Only if we have complete samples
                    num_samples = len(buffer) // 2
                    frame = rtc.AudioFrame(
                        data=buffer,
                        sample_rate=self._sample_rate,
                        num_channels=1,
                        samples_per_channel=num_samples,
                    )
                    frame_count += 1
                    yield frame
                else:
                    logger.warning("CartesiaTTS: discarding %d incomplete bytes", len(buffer))
            
            logger.debug("CartesiaTTS: HTTP synthesis complete (%d frames)", frame_count)
    
    async def synthesize_stream_from_iterator(
        self,
        text_iterator: AsyncIterable[str],
    ) -> AsyncIterable[rtc.AudioFrame]:
        """
        Synthesize audio from a streaming text source with internal chunking.
        
        The TTS handles buffering and chunking based on the configured strategy:
        - SENTENCE: Buffer until punctuation (. ! ? \\n), then synthesize
        - WORD: Buffer until word boundary (space), then synthesize
        - IMMEDIATE: Synthesize as soon as min_chunk_size is reached
        
        Args:
            text_iterator: Async iterator yielding text tokens/chunks
            
        Yields:
            Audio frames as they are synthesized
        """
        self._check_closed()
        self._reset_cancel()
        
        buffer = ""
        sentence_endings = ('.', '!', '?', '\n')
        chunks_sent = 0
        audio_frames_yielded = 0
        logger.debug("CartesiaTTS: starting streaming synthesis (strategy=%s)", self._chunking_strategy.value)

        async for token in text_iterator:
            if self._check_cancelled():
                break

            buffer += token

            should_flush = False

            if self._chunking_strategy == ChunkingStrategy.IMMEDIATE:
                should_flush = len(buffer) >= self._min_chunk_size

            elif self._chunking_strategy == ChunkingStrategy.SENTENCE:
                should_flush = (
                    buffer
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
                    logger.debug("CartesiaTTS: synthesizing chunk %d: %r", chunks_sent, chunk[:60])
                    async for audio_frame in self.synthesize_stream(chunk):
                        if self._check_cancelled():
                            return
                        audio_frames_yielded += 1
                        yield audio_frame
                buffer = ""

        if buffer.strip() and not self._check_cancelled():
            chunks_sent += 1
            logger.debug("CartesiaTTS: synthesizing final chunk %d: %r", chunks_sent, buffer.strip()[:60])
            async for audio_frame in self.synthesize_stream(buffer.strip()):
                if self._check_cancelled():
                    return
                audio_frames_yielded += 1
                yield audio_frame

        logger.info("CartesiaTTS: streaming synthesis complete (%d chunks, %d audio frames)", chunks_sent, audio_frames_yielded)
    
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
        """Close and cleanup."""
        await super().close()
        
        if self._session:
            await self._session.close()
            self._session = None
