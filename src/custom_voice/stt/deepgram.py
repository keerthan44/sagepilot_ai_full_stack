"""Deepgram STT implementation with WebSocket and HTTP support."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import AsyncIterable
from typing import Any, Literal
from urllib.parse import urlencode

import aiohttp
from livekit import rtc

from ..protocols import TranscriptSegment
from .base import BaseSTT

logger = logging.getLogger("custom-agent")


def _to_deepgram_url(opts: dict, base_url: str, *, websocket: bool) -> str:
    """
    Convert options to Deepgram URL.
    
    Args:
        opts: Query parameters
        base_url: Base API URL
        websocket: Whether to use WebSocket protocol
        
    Returns:
        Complete Deepgram API URL
    """
    # Don't modify the original opts
    opts = opts.copy()
    
    # Lowercase bools
    opts = {k: str(v).lower() if isinstance(v, bool) else v for k, v in opts.items()}
    
    # Convert protocol if needed
    if websocket and base_url.startswith("http"):
        base_url = base_url.replace("http", "ws", 1)
    elif not websocket and base_url.startswith("ws"):
        base_url = base_url.replace("ws", "http", 1)
    
    return f"{base_url}?{urlencode(opts, doseq=True)}"


class DeepgramSTT(BaseSTT):
    """
    Deepgram Speech-to-Text implementation.
    
    Supports both WebSocket (streaming) and HTTP (batch) transports.
    """
    
    def __init__(
        self,
        *,
        model: str = "nova-3",
        language: str | None = "multi",
        transport: Literal["websocket", "http"] = "websocket",
        api_key: str | None = None,
        base_url: str = "https://api.deepgram.com/v1/listen",
        sample_rate: int = 16000,
        interim_results: bool = True,
        punctuate: bool = True,
        smart_format: bool = False,
        filler_words: bool = True,
        vad_events: bool = True,
    ):
        """
        Initialize Deepgram STT.
        
        Args:
            model: Deepgram model (e.g., "nova-3", "nova-2")
            language: Language code or "multi" for multilingual
            transport: Transport protocol ("websocket" or "http")
            api_key: Deepgram API key (or set DEEPGRAM_API_KEY env var)
            base_url: Base API URL
            sample_rate: Audio sample rate in Hz
            interim_results: Return interim results (WebSocket only)
            punctuate: Add punctuation to transcripts
            smart_format: Apply smart formatting
            filler_words: Include filler words (um, uh, etc.)
            vad_events: Enable VAD events
        """
        super().__init__(
            model=model,
            language=language,
            sample_rate=sample_rate,
            interim_results=interim_results,
        )
        
        # Get API key
        self._api_key = api_key or os.environ.get("DEEPGRAM_API_KEY")
        if not self._api_key:
            raise ValueError(
                "Deepgram API key is required. Set DEEPGRAM_API_KEY environment "
                "variable or pass api_key parameter."
            )
        
        self._transport = transport
        self._base_url = base_url
        self._punctuate = punctuate
        self._smart_format = smart_format
        self._filler_words = filler_words
        self._vad_events = vad_events
        
        self._session: aiohttp.ClientSession | None = None
    
    def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session
    
    def _build_config(self, *, websocket: bool = False) -> dict[str, Any]:
        """Build Deepgram configuration parameters.

        Note: detect_language is NOT supported by Deepgram's live/streaming WebSocket
        endpoint. When websocket=True, language detection is silently disabled and the
        language parameter is omitted (Deepgram defaults to 'en-US').
        """
        config: dict[str, Any] = {
            "model": self._model,
            "punctuate": self._punctuate,
            "smart_format": self._smart_format,
            "filler_words": self._filler_words,
            "vad_events": self._vad_events,
            "encoding": "linear16",
            "sample_rate": self._sample_rate,
            "channels": 1,
        }

        if websocket:
            # Deepgram streaming WS does not support detect_language.
            # If a specific language was requested, include it; otherwise omit
            # (Deepgram defaults to 'en-US').
            if self._language and self._language != "multi":
                config["language"] = self._language
            elif self._language == "multi":
                logger.warning(
                    "DeepgramSTT: language='multi' (detect_language) is not supported in "
                    "WebSocket/streaming mode. Language parameter will be omitted; "
                    "Deepgram will default to 'en-US'. Use transport='http' for language detection."
                )
            config["interim_results"] = self._interim_results
        else:
            # HTTP batch mode supports detect_language
            if self._language and self._language != "multi":
                config["language"] = self._language
            elif self._language == "multi":
                config["detect_language"] = True

        return config
    
    async def recognize_stream(
        self,
        audio_stream: AsyncIterable[rtc.AudioFrame],
    ) -> AsyncIterable[TranscriptSegment]:
        """
        Recognize speech from audio stream.
        
        Args:
            audio_stream: Async iterable of audio frames
            
        Yields:
            TranscriptSegment objects with interim and final results
        """
        self._check_closed()
        
        if self._transport == "websocket":
            async for segment in self._recognize_websocket(audio_stream):
                yield segment
        else:
            async for segment in self._recognize_http(audio_stream):
                yield segment
    
    async def _recognize_websocket(
        self,
        audio_stream: AsyncIterable[rtc.AudioFrame],
    ) -> AsyncIterable[TranscriptSegment]:
        """Recognize using WebSocket transport.

        Mirrors the LiveKit Deepgram plugin behaviour:
        - Audio is buffered into fixed 50 ms chunks before sending.
        - A KeepAlive message is sent every 5 s to prevent the server from
          closing an idle connection during silence.
        - detect_language is NOT sent (not supported in streaming mode).
        """
        config = self._build_config(websocket=True)
        url = _to_deepgram_url(config, self._base_url, websocket=True)

        session = self._get_session()
        logger.debug("DeepgramSTT: connecting to WebSocket (model=%s, url=%s)", self._model, url)

        async with session.ws_connect(
            url,
            headers={"Authorization": f"Token {self._api_key}"},
        ) as ws:
            logger.info("DeepgramSTT: WebSocket connected")
            frames_sent = 0
            bytes_sent = 0

            # Buffer audio into 50 ms chunks (same as the LiveKit Deepgram plugin)
            samples_50ms = self._sample_rate // 20  # e.g. 800 samples at 16 kHz
            audio_buf: list[bytes] = []
            audio_buf_samples = 0

            async def send_audio() -> None:
                nonlocal frames_sent, bytes_sent, audio_buf, audio_buf_samples
                try:
                    async for frame in audio_stream:
                        if ws.closed:
                            break
                        audio_buf.append(frame.data.tobytes())
                        audio_buf_samples += frame.samples_per_channel

                        # Flush whenever we have accumulated ≥ 50 ms of audio
                        while audio_buf_samples >= samples_50ms:
                            chunk = b"".join(audio_buf)
                            # Take exactly samples_50ms * 2 bytes (int16)
                            send_bytes = samples_50ms * 2
                            await ws.send_bytes(chunk[:send_bytes])
                            bytes_sent += send_bytes
                            frames_sent += 1
                            if frames_sent == 1:
                                logger.debug("DeepgramSTT: first 50 ms chunk sent to Deepgram")
                            elif frames_sent % 200 == 0:
                                logger.debug(
                                    "DeepgramSTT: sent %d chunks (~%.1f s) to Deepgram",
                                    frames_sent,
                                    frames_sent * 0.05,
                                )
                            remaining = chunk[send_bytes:]
                            audio_buf = [remaining] if remaining else []
                            audio_buf_samples -= samples_50ms

                    # Flush any leftover audio
                    if audio_buf:
                        remaining_chunk = b"".join(audio_buf)
                        if remaining_chunk:
                            await ws.send_bytes(remaining_chunk)

                    logger.debug("DeepgramSTT: audio stream exhausted, sending CloseStream")
                    await ws.send_str(json.dumps({"type": "CloseStream"}))
                except Exception:
                    logger.exception("DeepgramSTT: error in send_audio task")

            async def keepalive() -> None:
                """Send KeepAlive every 5 s so Deepgram doesn't close idle connections."""
                try:
                    while True:
                        await asyncio.sleep(5)
                        if ws.closed:
                            break
                        await ws.send_str(json.dumps({"type": "KeepAlive"}))
                        logger.debug("DeepgramSTT: sent KeepAlive")
                except asyncio.CancelledError:
                    pass
                except Exception:
                    logger.warning("DeepgramSTT: KeepAlive task exited unexpectedly")

            send_task = asyncio.create_task(send_audio())
            keepalive_task = asyncio.create_task(keepalive())

            try:
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)

                        if data.get("type") == "Results":
                            channel = data.get("channel", {})
                            alternatives = channel.get("alternatives", [])

                            if alternatives:
                                alt = alternatives[0]
                                transcript = alt.get("transcript", "")

                                if transcript:
                                    is_final = data.get("is_final", False)
                                    confidence = alt.get("confidence", 1.0)
                                    logger.debug(
                                        "DeepgramSTT: received %s transcript: %r (conf=%.2f)",
                                        "final" if is_final else "interim",
                                        transcript,
                                        confidence,
                                    )
                                    yield TranscriptSegment(
                                        text=transcript,
                                        is_final=is_final,
                                        confidence=confidence,
                                        language=self._language,
                                    )

                    elif msg.type in (
                        aiohttp.WSMsgType.CLOSED,
                        aiohttp.WSMsgType.CLOSE,
                        aiohttp.WSMsgType.CLOSING,
                    ):
                        logger.debug("DeepgramSTT: WebSocket closed by server")
                        break

                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        logger.error("DeepgramSTT: WebSocket error: %s", msg.data)
                        break
            finally:
                logger.debug(
                    "DeepgramSTT: WebSocket closing (chunks_sent=%d, ~%.1f s of audio)",
                    frames_sent,
                    frames_sent * 0.05,
                )
                for task in (send_task, keepalive_task):
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
    
    async def _recognize_http(
        self,
        audio_stream: AsyncIterable[rtc.AudioFrame],
    ) -> AsyncIterable[TranscriptSegment]:
        """Recognize using HTTP transport."""
        frames = []
        async for frame in audio_stream:
            frames.append(frame)

        if not frames:
            return

        logger.debug("DeepgramSTT: HTTP batch recognition (%d frames collected)", len(frames))

        combined = rtc.combine_audio_frames(frames)
        audio_data = combined.to_wav_bytes()

        config = self._build_config(websocket=False)
        url = _to_deepgram_url(config, self._base_url, websocket=False)
        
        session = self._get_session()
        
        # Make HTTP request
        async with session.post(
            url,
            data=audio_data,
            headers={
                "Authorization": f"Token {self._api_key}",
                "Content-Type": "audio/wav",
            },
        ) as response:
            response.raise_for_status()
            result = await response.json()
            
            # Parse response
            results = result.get("results", {})
            channels = results.get("channels", [])
            
            if channels:
                alternatives = channels[0].get("alternatives", [])
                if alternatives:
                    alt = alternatives[0]
                    transcript = alt.get("transcript", "")
                    
                    if transcript:
                        confidence = alt.get("confidence", 1.0)
                        
                        yield TranscriptSegment(
                            text=transcript,
                            is_final=True,
                            confidence=confidence,
                            language=self._language,
                        )
    
    async def close(self) -> None:
        """Close and cleanup."""
        await super().close()
        
        if self._session:
            await self._session.close()
            self._session = None
