"""Consumer classes for event-driven session architecture."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from livekit import rtc

from .events import (
    Event,
    EventType,
    AudioFrameData,
    VADSignalData,
    TranscriptData,
    TurnProbabilityData,
)

logger = logging.getLogger("custom-agent")

if TYPE_CHECKING:
    from .audio_pipeline import AudioPipeline
    from .protocols import (
        VADProtocol,
        STTProtocol,
        AudioTurnDetectorProtocol,
    )
    from .session import CustomAgentSession


class BaseConsumer(ABC):
    """Base class for all consumers."""
    
    def __init__(self, event_bus: asyncio.Queue[Event]):
        self._event_bus = event_bus
        self._closed = False
    
    @abstractmethod
    async def run(self) -> None:
        """Main consumer loop."""
        ...
    
    def close(self) -> None:
        """Signal consumer to close."""
        self._closed = True


class AudioDistributor(BaseConsumer):
    """
    Distributes incoming audio frames to all consumers.
    Implements zero-copy fan-out pattern.
    
    CRITICAL: The same rtc.AudioFrame object is passed to all consumer queues.
    This is safe because all consumers treat frames as read-only.
    """
    
    def __init__(
        self,
        event_bus: asyncio.Queue[Event],
        audio_pipeline: AudioPipeline,
        vad_queue: asyncio.Queue[rtc.AudioFrame],
        stt_queue: asyncio.Queue[rtc.AudioFrame],
    ):
        super().__init__(event_bus)
        self._audio_pipeline = audio_pipeline
        self._vad_queue = vad_queue
        self._stt_queue = stt_queue
    
    async def run(self) -> None:
        """Distribute audio frames to all consumers."""
        frame_count = 0
        logger.debug("AudioDistributor: starting, waiting for audio frames")
        async for audio_frame in self._audio_pipeline.input_stream():
            if self._closed:
                break

            frame_count += 1
            if frame_count == 1:
                logger.info(
                    "AudioDistributor: first audio frame received (sample_rate=%d, channels=%d, samples=%d)",
                    audio_frame.sample_rate,
                    audio_frame.num_channels,
                    audio_frame.samples_per_channel,
                )
            elif frame_count % 500 == 0:
                logger.debug("AudioDistributor: distributed %d frames so far", frame_count)

            await self._event_bus.put(Event(
                type=EventType.AUDIO_FRAME,
                data=AudioFrameData(frame=audio_frame)
            ))

            await self._vad_queue.put(audio_frame)
            await self._stt_queue.put(audio_frame)

        logger.debug("AudioDistributor: input stream ended after %d frames", frame_count)


class VADConsumer(BaseConsumer):
    """
    Consumes audio frames, processes with VAD, emits VAD events.
    
    Receives frames from vad_queue, processes them, and emits:
    - VAD_INFERENCE_DONE (every frame)
    - VAD_START_OF_SPEECH (on speech start)
    - VAD_END_OF_SPEECH (on speech end)
    
    Also feeds audio + VAD probability to audio turn detector queue if configured.
    """
    
    def __init__(
        self,
        event_bus: asyncio.Queue[Event],
        vad: VADProtocol,
        vad_queue: asyncio.Queue[rtc.AudioFrame],
        audio_turn_queue: asyncio.Queue[tuple[rtc.AudioFrame, float]] | None = None,
    ):
        super().__init__(event_bus)
        self._vad = vad
        self._vad_queue = vad_queue
        self._audio_turn_queue = audio_turn_queue
        self._speaking = False
    
    async def run(self) -> None:
        """Process audio with VAD and emit events."""
        frames_processed = 0
        speech_frames = 0
        logger.debug("VADConsumer: starting")
        while not self._closed:
            try:
                audio_frame = await self._vad_queue.get()

                vad_signal = await self._vad.process_audio(audio_frame)
                frames_processed += 1

                await self._event_bus.put(Event(
                    type=EventType.VAD_INFERENCE_DONE,
                    data=VADSignalData(signal=vad_signal)
                ))

                if self._audio_turn_queue:
                    await self._audio_turn_queue.put((audio_frame, vad_signal.probability))

                if vad_signal.is_speech and not self._speaking:
                    self._speaking = True
                    speech_frames = 0
                    logger.info(
                        "VAD: speech started (prob=%.3f, frames_processed=%d)",
                        vad_signal.probability,
                        frames_processed,
                    )
                    await self._event_bus.put(Event(
                        type=EventType.VAD_START_OF_SPEECH,
                        data=VADSignalData(signal=vad_signal)
                    ))
                elif vad_signal.is_speech and self._speaking:
                    # Continue speech - emit inference event for interruption detection
                    speech_frames += 1
                    if speech_frames % 50 == 0:  # Log every 50 frames (~500ms)
                        logger.debug(
                            "VAD: continuous speech (prob=%.3f, speech_frames=%d)",
                            vad_signal.probability,
                            speech_frames,
                        )
                elif not vad_signal.is_speech and self._speaking:
                    self._speaking = False
                    logger.info(
                        "VAD: speech ended (prob=%.3f, frames_processed=%d, speech_frames=%d)",
                        vad_signal.probability,
                        frames_processed,
                        speech_frames,
                    )
                    await self._event_bus.put(Event(
                        type=EventType.VAD_END_OF_SPEECH,
                        data=VADSignalData(signal=vad_signal)
                    ))

            except asyncio.CancelledError:
                break

        logger.debug("VADConsumer: stopped after processing %d frames", frames_processed)


class STTConsumer(BaseConsumer):
    """
    Consumes audio frames, processes with STT, emits transcript events.
    
    Receives frames from stt_queue, feeds them to STT streaming recognition,
    and emits:
    - STT_INTERIM_TRANSCRIPT (partial transcripts)
    - STT_FINAL_TRANSCRIPT (final transcripts)
    """
    
    def __init__(
        self,
        event_bus: asyncio.Queue[Event],
        stt: STTProtocol,
        stt_queue: asyncio.Queue[rtc.AudioFrame],
    ):
        super().__init__(event_bus)
        self._stt = stt
        self._stt_queue = stt_queue
    
    async def run(self) -> None:
        """Process audio with STT and emit transcript events."""
        frames_sent = 0

        async def audio_stream_generator():
            nonlocal frames_sent
            while not self._closed:
                try:
                    frame = await self._stt_queue.get()
                    frames_sent += 1
                    if frames_sent == 1:
                        logger.debug("STTConsumer: first frame flowing to STT")
                    yield frame
                except asyncio.CancelledError:
                    break

        logger.debug("STTConsumer: starting STT stream")
        try:
            async for transcript in self._stt.recognize_stream(audio_stream_generator()):
                if transcript.is_final:
                    logger.info(
                        "STT final: %r (confidence=%.2f)",
                        transcript.text,
                        transcript.confidence,
                    )
                    await self._event_bus.put(Event(
                        type=EventType.STT_FINAL_TRANSCRIPT,
                        data=TranscriptData(segment=transcript)
                    ))
                else:
                    logger.debug("STT interim: %r", transcript.text)
                    await self._event_bus.put(Event(
                        type=EventType.STT_INTERIM_TRANSCRIPT,
                        data=TranscriptData(segment=transcript)
                    ))
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("STTConsumer: error in STT stream after %d frames sent", frames_sent)

        logger.debug("STTConsumer: STT stream ended (%d frames sent)", frames_sent)


class AudioTurnConsumer(BaseConsumer):
    """
    Consumes audio frames + VAD probabilities, emits turn probability events.
    
    Receives (audio_frame, vad_probability) tuples from audio_turn_queue,
    processes with audio turn detector, and emits:
    - AUDIO_TURN_PROBABILITY events
    """
    
    def __init__(
        self,
        event_bus: asyncio.Queue[Event],
        audio_turn_detector: AudioTurnDetectorProtocol,
        audio_turn_queue: asyncio.Queue[tuple[rtc.AudioFrame, float]],
    ):
        super().__init__(event_bus)
        self._audio_turn_detector = audio_turn_detector
        self._audio_turn_queue = audio_turn_queue
    
    async def run(self) -> None:
        """Process audio with turn detector and emit events."""
        while not self._closed:
            try:
                audio_frame, vad_prob = await self._audio_turn_queue.get()
                
                turn_prob = await self._audio_turn_detector.process_audio(
                    audio_frame, vad_prob
                )
                
                await self._event_bus.put(Event(
                    type=EventType.AUDIO_TURN_PROBABILITY,
                    data=TurnProbabilityData(probability=turn_prob, source="audio")
                ))
                
            except asyncio.CancelledError:
                break


class EventCoordinator(BaseConsumer):
    """
    Central event coordinator - reacts to all events.
    Implements state-driven coordination logic.
    
    This is the "brain" that reacts to events from all consumers
    and coordinates the overall agent behavior.
    """
    
    def __init__(
        self,
        event_bus: asyncio.Queue[Event],
        session: CustomAgentSession,  # type: ignore[name-defined]
    ):
        super().__init__(event_bus)
        self._session = session
    
    async def run(self) -> None:
        """Main event coordination loop."""
        # Track the active generate_reply task so we never run two concurrently.
        self._reply_task: asyncio.Task | None = None

        while not self._closed:
            try:
                event = await self._event_bus.get()

                if event.type == EventType.VAD_INFERENCE_DONE:
                    await self._on_vad_inference(event.data)

                elif event.type == EventType.VAD_START_OF_SPEECH:
                    await self._on_start_of_speech(event.data)

                elif event.type == EventType.VAD_END_OF_SPEECH:
                    await self._on_end_of_speech(event.data)

                elif event.type == EventType.STT_FINAL_TRANSCRIPT:
                    await self._on_final_transcript(event.data)

                elif event.type == EventType.AUDIO_TURN_PROBABILITY:
                    await self._on_audio_turn_probability(event.data)

                elif event.type == EventType.TEXT_TURN_PROBABILITY:
                    await self._on_text_turn_probability(event.data)

                elif event.type == EventType.INTERRUPTION_DETECTED:
                    await self._on_interruption(event.data)

                elif event.type == EventType.SHUTDOWN:
                    break

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("EventCoordinator: unhandled error processing event %s", event.type)
    
    async def _on_vad_inference(self, data: VADSignalData) -> None:
        """Handle VAD inference event - check for interruptions during agent speech."""
        # Only check for interruptions when agent is busy (thinking or speaking)
        if self._session._agent_state in ("thinking", "speaking"):
            # Only process if user is actually speaking (VAD detected speech)
            if data.signal.is_speech:
                if self._session._interruption_handler.process_vad_signal(data.signal):
                    logger.info("EventCoordinator: interruption detected via VAD inference")
                    await self._event_bus.put(Event(
                        type=EventType.INTERRUPTION_DETECTED,
                        data=None
                    ))
    
    async def _on_start_of_speech(self, data: VADSignalData) -> None:
        """Handle start of speech event - marks user as speaking."""
        logger.debug("EventCoordinator: user started speaking (agent_state=%s)", self._session._agent_state)
        self._session._user_state = "speaking"
        # Note: interruption detection is handled by _on_vad_inference for every frame

    async def _on_end_of_speech(self, data: VADSignalData) -> None:
        """Handle end of speech event."""
        logger.debug("EventCoordinator: user stopped speaking")
        self._session._user_state = "listening"

        # Trigger turn evaluation when user stops speaking, but only if we have a transcript.
        # If no transcript yet, _on_final_transcript will handle it.
        if self._session._current_transcript:
            logger.debug("EventCoordinator: evaluating turn complete (user stopped speaking)")
            await self._session._evaluate_turn_complete_async()

    async def _on_final_transcript(self, data: TranscriptData) -> None:
        """Handle final transcript event."""
        transcript = data.segment.text
        logger.info("EventCoordinator: final transcript received: %r", transcript)
        self._session._current_transcript += f" {transcript}"
        self._session._current_transcript = self._session._current_transcript.strip()

        if self._session._text_turn_detector:
            context = self._session._conversation_context.get_last_n_turns(
                self._session._text_turn_detector._context_window_turns
            )
            text_turn_prob = await self._session._text_turn_detector.process_transcript(
                transcript=self._session._current_transcript,
                is_final=True,
                conversation_context=context
            )

            await self._event_bus.put(Event(
                type=EventType.TEXT_TURN_PROBABILITY,
                data=TurnProbabilityData(probability=text_turn_prob, source="text")
            ))

        # If user has already stopped speaking, trigger evaluation now.
        # Otherwise, _on_end_of_speech will handle it.
        if self._session._user_state != "speaking":
            logger.debug("EventCoordinator: evaluating turn complete (user already stopped)")
            await self._session._evaluate_turn_complete_async()
    
    async def _on_audio_turn_probability(self, data: TurnProbabilityData) -> None:
        """Handle audio turn probability event."""
        self._session._audio_turn_probability = data.probability
    
    async def _on_text_turn_probability(self, data: TurnProbabilityData) -> None:
        """Handle text turn probability event."""
        self._session._text_turn_probability = data.probability
    
    async def _on_interruption(self, data: Any) -> None:
        """Handle interruption event."""
        logger.info("EventCoordinator: handling interruption event")
        await self._session._handle_interruption()
