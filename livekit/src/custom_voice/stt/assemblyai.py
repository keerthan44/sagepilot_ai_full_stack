"""AssemblyAI STT implementation with WebSocket support."""

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
from livekit.agents.utils import audio as audio_utils

from ..protocols import TranscriptSegment
from .base import BaseSTT

logger = logging.getLogger("custom-agent")


class AssemblyAISTT(BaseSTT):
    """
    AssemblyAI Speech-to-Text implementation.
    
    Supports WebSocket streaming with real-time transcription.
    """
    
    def __init__(
        self,
        *,
        model: Literal[
            "universal-streaming-english",
            "universal-streaming-multilingual",
            "u3-rt-pro",
        ] = "universal-streaming-english",
        language: str | None = None,
        api_key: str | None = None,
        base_url: str = "wss://streaming.assemblyai.com",
        sample_rate: int = 16000,
        interim_results: bool = True,
        encoding: Literal["pcm_s16le", "pcm_mulaw"] = "pcm_s16le",
        buffer_size_seconds: float = 0.05,
        language_detection: bool | None = None,
        end_of_turn_confidence_threshold: float | None = None,
        min_turn_silence: int | None = None,
        max_turn_silence: int | None = None,
        format_turns: bool | None = None,
        keyterms_prompt: list[str] | None = None,
        prompt: str | None = None,
        vad_threshold: float | None = None,
        speaker_labels: bool | None = None,
        max_speakers: int | None = None,
    ):
        """
        Initialize AssemblyAI STT.
        
        Args:
            model: AssemblyAI model (e.g., "universal-streaming-english", "u3-rt-pro")
            language: Language code (None for auto-detect)
            api_key: AssemblyAI API key (or set ASSEMBLYAI_API_KEY env var)
            base_url: Base WebSocket URL
            sample_rate: Audio sample rate in Hz
            interim_results: Return interim results
            encoding: Audio encoding format
            buffer_size_seconds: Audio buffer size in seconds (default 0.05 = 50ms)
            language_detection: Enable language detection
            end_of_turn_confidence_threshold: Confidence threshold for end of turn
            min_turn_silence: Minimum silence in ms before finalizing turn
            max_turn_silence: Maximum silence in ms before finalizing turn
            format_turns: Apply turn formatting
            keyterms_prompt: List of key terms to boost recognition
            prompt: Context prompt for better recognition
            vad_threshold: Voice activity detection threshold (0-1)
            speaker_labels: Enable speaker diarization
            max_speakers: Maximum number of speakers to detect
        """
        super().__init__(
            model=model,
            language=language,
            sample_rate=sample_rate,
            interim_results=interim_results,
        )
        
        # Get API key
        self._api_key = api_key or os.environ.get("ASSEMBLYAI_API_KEY")
        if not self._api_key:
            raise ValueError(
                "AssemblyAI API key is required. Set ASSEMBLYAI_API_KEY environment "
                "variable or pass api_key parameter."
            )
        
        self._base_url = base_url
        self._encoding = encoding
        self._buffer_size_seconds = buffer_size_seconds
        self._language_detection = language_detection
        self._end_of_turn_confidence_threshold = end_of_turn_confidence_threshold
        self._min_turn_silence = min_turn_silence
        self._max_turn_silence = max_turn_silence
        self._format_turns = format_turns
        self._keyterms_prompt = keyterms_prompt
        self._prompt = prompt
        self._vad_threshold = vad_threshold
        self._speaker_labels = speaker_labels
        self._max_speakers = max_speakers
        
        self._session: aiohttp.ClientSession | None = None
        self._session_id: str | None = None
        self._expires_at: int | None = None
    
    def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session
    
    def _build_config(self) -> dict[str, Any]:
        """Build AssemblyAI configuration parameters."""
        # Set defaults based on model
        if self._model == "u3-rt-pro":
            min_silence = self._min_turn_silence if self._min_turn_silence is not None else 100
            max_silence = self._max_turn_silence if self._max_turn_silence is not None else min_silence
        else:
            min_silence = self._min_turn_silence
            max_silence = self._max_turn_silence
        
        # Determine language detection default
        if self._language_detection is not None:
            lang_detect = self._language_detection
        elif "multilingual" in self._model or self._model == "u3-rt-pro":
            lang_detect = True
        else:
            lang_detect = False
        
        config = {
            "sample_rate": self._sample_rate,
            "encoding": self._encoding,
            "speech_model": self._model,
        }
        
        # Add optional parameters
        if self._format_turns is not None:
            config["format_turns"] = self._format_turns
        if self._end_of_turn_confidence_threshold is not None:
            config["end_of_turn_confidence_threshold"] = self._end_of_turn_confidence_threshold
        if min_silence is not None:
            config["min_turn_silence"] = min_silence
        if max_silence is not None:
            config["max_turn_silence"] = max_silence
        if self._keyterms_prompt is not None:
            config["keyterms_prompt"] = json.dumps(self._keyterms_prompt)
        if lang_detect is not None:
            config["language_detection"] = lang_detect
        if self._prompt is not None:
            config["prompt"] = self._prompt
        if self._vad_threshold is not None:
            config["vad_threshold"] = self._vad_threshold
        if self._speaker_labels is not None:
            config["speaker_labels"] = self._speaker_labels
        if self._max_speakers is not None:
            config["max_speakers"] = self._max_speakers
        
        return config
    
    def _build_url(self) -> str:
        """Build AssemblyAI WebSocket URL with query parameters."""
        config = self._build_config()
        
        # Convert booleans to strings
        filtered_config = {
            k: ("true" if v else "false") if isinstance(v, bool) else v
            for k, v in config.items()
            if v is not None
        }
        
        return f"{self._base_url}/v3/ws?{urlencode(filtered_config)}"
    
    async def recognize_stream(
        self,
        audio_stream: AsyncIterable[rtc.AudioFrame],
    ) -> AsyncIterable[TranscriptSegment]:
        """
        Recognize speech from audio stream using WebSocket.
        
        Args:
            audio_stream: Async iterable of audio frames
            
        Yields:
            TranscriptSegment objects with interim and final results
        """
        self._check_closed()
        
        url = self._build_url()
        session = self._get_session()
        
        logger.debug("AssemblyAISTT: connecting to WebSocket (model=%s, url=%s)", self._model, url)
        
        async with session.ws_connect(
            url,
            headers={
                "Authorization": self._api_key,
                "Content-Type": "application/json",
                "User-Agent": "AssemblyAI/1.0 (integration=CustomVoiceStack)",
            },
        ) as ws:
            logger.info("AssemblyAISTT: WebSocket connected")
            
            frames_sent = 0
            
            # Buffer audio into chunks based on buffer_size_seconds
            samples_per_buffer = int(self._sample_rate * self._buffer_size_seconds)
            audio_bstream = audio_utils.AudioByteStream(
                sample_rate=self._sample_rate,
                num_channels=1,
                samples_per_channel=samples_per_buffer,
            )
            
            async def send_audio() -> None:
                """Send audio frames to AssemblyAI."""
                nonlocal frames_sent
                try:
                    async for frame in audio_stream:
                        if ws.closed:
                            break
                        
                        # Buffer and rebatch audio
                        buffered_frames = audio_bstream.write(frame.data.tobytes())
                        
                        for buffered_frame in buffered_frames:
                            await ws.send_bytes(buffered_frame.data.tobytes())
                            frames_sent += 1
                            
                            if frames_sent == 1:
                                logger.debug(
                                    "AssemblyAISTT: first %.0f ms chunk sent to AssemblyAI",
                                    self._buffer_size_seconds * 1000,
                                )
                            elif frames_sent % 200 == 0:
                                logger.debug(
                                    "AssemblyAISTT: sent %d chunks (~%.1f s) to AssemblyAI",
                                    frames_sent,
                                    frames_sent * self._buffer_size_seconds,
                                )
                    
                    # Flush any remaining audio
                    remaining_frames = audio_bstream.flush()
                    for frame in remaining_frames:
                        await ws.send_bytes(frame.data.tobytes())
                    
                    logger.debug("AssemblyAISTT: audio stream exhausted, sending Terminate")
                    await ws.send_str(json.dumps({"type": "Terminate"}))
                except Exception:
                    logger.exception("AssemblyAISTT: error in send_audio task")
            
            send_task = asyncio.create_task(send_audio())
            
            try:
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        message_type = data.get("type")
                        
                        if message_type == "Begin":
                            self._session_id = data.get("id")
                            self._expires_at = data.get("expires_at")
                            logger.info(
                                "AssemblyAISTT: session started (id=%s, expires_at=%s)",
                                self._session_id,
                                self._expires_at,
                            )
                        
                        elif message_type == "SpeechStarted":
                            logger.debug("AssemblyAISTT: speech started event")
                        
                        elif message_type == "Termination":
                            audio_duration = data.get("audio_duration_seconds")
                            session_duration = data.get("session_duration_seconds")
                            logger.debug(
                                "AssemblyAISTT: session terminated (audio=%.2fs, session=%.2fs)",
                                audio_duration or 0,
                                session_duration or 0,
                            )
                        
                        elif message_type == "Turn":
                            # Process turn message
                            words = data.get("words", [])
                            end_of_turn = data.get("end_of_turn", False)
                            end_of_turn_confidence = data.get("end_of_turn_confidence")
                            utterance = data.get("utterance", "")
                            transcript = data.get("transcript", "")
                            language_code = data.get("language_code", "en")
                            
                            # Calculate confidence from words
                            confidence = 0.0
                            if words:
                                confidence = sum(w.get("confidence", 0.0) for w in words) / len(words)
                            
                            # Emit interim transcript (cumulative words)
                            if words and transcript:
                                logger.debug(
                                    "AssemblyAISTT: received interim transcript: %r (conf=%.2f, eot_conf=%s)",
                                    transcript,
                                    confidence,
                                    end_of_turn_confidence,
                                )
                                yield TranscriptSegment(
                                    text=transcript,
                                    is_final=False,
                                    confidence=confidence,
                                    language=language_code,
                                )
                            
                            # Emit final transcript when end of turn is detected
                            if end_of_turn and transcript:
                                logger.debug(
                                    "AssemblyAISTT: received final transcript: %r (conf=%.2f, eot_conf=%.2f)",
                                    transcript,
                                    confidence,
                                    end_of_turn_confidence or 0.0,
                                )
                                yield TranscriptSegment(
                                    text=transcript,
                                    is_final=True,
                                    confidence=confidence,
                                    language=language_code,
                                )
                    
                    elif msg.type in (
                        aiohttp.WSMsgType.CLOSED,
                        aiohttp.WSMsgType.CLOSE,
                        aiohttp.WSMsgType.CLOSING,
                    ):
                        logger.debug("AssemblyAISTT: WebSocket closed by server")
                        break
                    
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        logger.error("AssemblyAISTT: WebSocket error: %s", msg.data)
                        break
            finally:
                logger.debug(
                    "AssemblyAISTT: WebSocket closing (chunks_sent=%d, ~%.1f s of audio)",
                    frames_sent,
                    frames_sent * self._buffer_size_seconds,
                )
                send_task.cancel()
                try:
                    await send_task
                except asyncio.CancelledError:
                    pass
    
    async def close(self) -> None:
        """Close and cleanup."""
        await super().close()
        
        if self._session:
            await self._session.close()
            self._session = None
