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
        base_url: str = "https://api.cartesia.ai/v1/tts",
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
            base_url: Base API URL
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
        
        # Convert base URL to WebSocket
        ws_url = self._base_url.replace("https://", "wss://").replace("http://", "ws://")
        
        async with session.ws_connect(
            ws_url,
            headers={"Authorization": f"Bearer {self._api_key}"},
        ) as ws:
            # Send configuration
            config = {
                "type": "config",
                "model": self._model,
                "voice": self._voice,
                "sample_rate": self._sample_rate,
                "output_format": "pcm_16000",
            }
            await ws.send_json(config)
            
            # Task to send text
            async def send_text():
                try:
                    if isinstance(text, str):
                        await ws.send_json({"type": "text", "text": text})
                    else:
                        async for chunk in text:
                            if self._check_cancelled():
                                break
                            await ws.send_json({"type": "text", "text": chunk})
                    
                    # Send end marker
                    await ws.send_json({"type": "end"})
                except Exception:
                    pass
            
            # Start sending text
            send_task = asyncio.create_task(send_text())
            
            try:
                # Receive audio
                async for msg in ws:
                    if self._check_cancelled():
                        break
                    
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        
                        if data.get("type") == "audio":
                            # Decode base64 audio
                            audio_b64 = data.get("data", "")
                            audio_bytes = base64.b64decode(audio_b64)
                            
                            # Convert to audio frame
                            audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
                            frame = rtc.AudioFrame(
                                data=audio_array,
                                sample_rate=self._sample_rate,
                                num_channels=1,
                                samples_per_channel=len(audio_array),
                            )
                            yield frame
                        
                        elif data.get("type") == "done":
                            break
                    
                    elif msg.type == aiohttp.WSMsgType.ERROR:
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
        """Synthesize using HTTP transport."""
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
        
        # Make HTTP request
        payload = {
            "model": self._model,
            "voice": self._voice,
            "text": full_text,
            "sample_rate": self._sample_rate,
            "output_format": "pcm_16000",
        }
        
        async with session.post(
            self._base_url,
            json=payload,
            headers={"Authorization": f"Bearer {self._api_key}"},
        ) as response:
            response.raise_for_status()
            result = await response.json()
            
            # Decode audio
            audio_b64 = result.get("audio", "")
            audio_bytes = base64.b64decode(audio_b64)
            
            # Convert to audio frame
            audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
            frame = rtc.AudioFrame(
                data=audio_array,
                sample_rate=self._sample_rate,
                num_channels=1,
                samples_per_channel=len(audio_array),
            )
            yield frame
    
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
