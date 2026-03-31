"""Custom Agent Session - Main orchestration layer.

Event-driven architecture using asyncio.Queue as event bus.
Components communicate via events, enabling parallel processing and loose coupling.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterable
from typing import TYPE_CHECKING, Literal

logger = logging.getLogger("custom-agent")

from livekit import rtc
from livekit.agents.utils import audio as audio_utils

from .audio_pipeline import AudioPipeline
from .config import InterruptionConfig, VoiceStackConfig
from .context import ConversationContext
from .events import Event, EventType, TurnCompleteData
from .interruption import InterruptionHandler
from .session_consumers import (
    AudioDistributor,
    AudioTurnConsumer,
    EventCoordinator,
    STTConsumer,
    VADConsumer,
)
from .turn_detection.aggregator import TurnAggregator

if TYPE_CHECKING:
    from .protocols import (
        AudioTurnDetectorProtocol,
        LLMProtocol,
        STTProtocol,
        TextTurnDetectorProtocol,
        TTSProtocol,
        VADProtocol,
    )


class CustomAgentSession:
    """
    Custom Agent Session - Event-driven orchestration.

    Uses asyncio.Queue as event bus with independent consumer tasks
    for VAD, STT, and turn detection that communicate via events.
    """

    def __init__(
        self,
        *,
        stt: STTProtocol,
        llm: LLMProtocol,
        tts: TTSProtocol,
        vad: VADProtocol,
        audio_turn_detector: AudioTurnDetectorProtocol | None = None,
        text_turn_detector: TextTurnDetectorProtocol | None = None,
        config: VoiceStackConfig | None = None,
    ):
        """
        Initialize custom agent session.

        Args:
            stt: Speech-to-text component
            llm: Large language model component
            tts: Text-to-speech component
            vad: Voice activity detection component
            audio_turn_detector: Optional audio-based turn detector
            text_turn_detector: Optional text-based turn detector
            config: Voice stack configuration
        """
        self._stt = stt
        self._llm = llm
        self._tts = tts
        self._vad = vad
        self._audio_turn_detector = audio_turn_detector
        self._text_turn_detector = text_turn_detector
        self._config = config

        self._audio_pipeline = AudioPipeline()
        self._conversation_context = ConversationContext()
        self._interruption_handler = InterruptionHandler(
            config=config.interruption if config else InterruptionConfig(),
            llm=llm,
            tts=tts,
        )

        if audio_turn_detector and text_turn_detector and config:
            self._turn_aggregator = TurnAggregator(
                strategy=config.turn_detection.aggregation_strategy,
                weights=config.turn_detection.weights,
            )
        else:
            self._turn_aggregator = None

        self._event_bus: asyncio.Queue[Event] = asyncio.Queue()

        self._vad_queue: asyncio.Queue[rtc.AudioFrame] = asyncio.Queue()
        self._stt_queue: asyncio.Queue[rtc.AudioFrame] = asyncio.Queue()
        self._audio_turn_queue: asyncio.Queue[tuple[rtc.AudioFrame, float]] | None = (
            asyncio.Queue() if audio_turn_detector else None
        )

        self._audio_distributor = AudioDistributor(
            self._event_bus,
            self._audio_pipeline,
            self._vad_queue,
            self._stt_queue,
        )
        self._vad_consumer = VADConsumer(
            self._event_bus,
            vad,
            self._vad_queue,
            self._audio_turn_queue,
        )
        self._stt_consumer = STTConsumer(
            self._event_bus,
            stt,
            self._stt_queue,
        )
        self._audio_turn_consumer = (
            AudioTurnConsumer(
                self._event_bus,
                audio_turn_detector,
                self._audio_turn_queue,
            )
            if audio_turn_detector and self._audio_turn_queue
            else None
        )
        self._event_coordinator = EventCoordinator(self._event_bus, self)

        self._user_state: Literal["listening", "speaking", "away"] = "listening"
        self._agent_state: Literal[
            "initializing", "listening", "thinking", "speaking"
        ] = "initializing"
        self._room: rtc.Room | None = None
        self._started = False
        self._closed = False

        self._speaking = False
        self._current_transcript = ""
        self._audio_turn_probability = 0.0
        self._text_turn_probability = 0.0
        self._audio_publishing = False  # Track if audio is actively being published
        self._generation_complete = asyncio.Event()  # Signal when TTS generation is done
        self._generation_complete.set()  # Initially set (no generation in progress)

        self._consumer_tasks: list[asyncio.Task] = []
        self._output_task: asyncio.Task | None = None
        # Keeps strong references to track-processing tasks so they aren't GC'd
        self._track_tasks: dict[str, asyncio.Task] = {}
        # Background task running the current generate_reply pipeline
        self._reply_task: asyncio.Task | None = None

        # Pre-created audio output source and track (published on room connect)
        self._audio_source: rtc.AudioSource | None = None
        self._audio_track: rtc.LocalAudioTrack | None = None
        self._audio_bstream: audio_utils.AudioByteStream | None = None

    async def start(self, room: rtc.Room, instructions: str | None = None) -> None:
        """
        Start the agent session and all consumer tasks.

        Args:
            room: LiveKit room to connect to
            instructions: System instructions for the LLM
        """
        if self._started:
            return

        self._room = room
        self._started = True

        if instructions:
            self._conversation_context.add_turn(
                role="system",
                content=instructions,
            )

        # Wire tool-use recording into the LLM so tool calls and results
        # appear in the transcript automatically.
        if hasattr(self._llm, "_on_tool_use") and self._llm._on_tool_use is None:

            async def _record_tool_use(
                calls: list[dict],
                results: list[dict],
            ) -> None:
                self._conversation_context.add_turn(
                    role="tool_call",
                    content="",  # no text content; data is in tool_calls
                    tool_calls=calls,
                )
                for r in results:
                    self._conversation_context.add_turn(
                        role="tool_result",
                        content=r["content"],
                        tool_call_id=r["tool_call_id"],
                        metadata={"name": r["name"]},
                    )

            self._llm._on_tool_use = _record_tool_use

        await self._audio_pipeline.start()

        # Pre-create the audio source and local track so they exist before the
        # room connects.  The track is published in _on_room_connected() once
        # ctx.connect() has completed.  This avoids the lazy-publish race where
        # publish_track() fails inside _output_audio_loop and silently kills the
        # output loop.
        tts_sample_rate: int = getattr(self._tts, "sample_rate", 24000)

        self._audio_source = rtc.AudioSource(
            sample_rate=tts_sample_rate, num_channels=1
        )
        self._audio_track = rtc.LocalAudioTrack.create_audio_track(
            "agent-voice", self._audio_source
        )
        logger.debug(
            "pre-created agent audio source (sample_rate=%d)",
            tts_sample_rate,
        )

        self._setup_room_handlers()

        self._consumer_tasks = [
            asyncio.create_task(self._audio_distributor.run()),
            asyncio.create_task(self._vad_consumer.run()),
            asyncio.create_task(self._stt_consumer.run()),
            asyncio.create_task(self._event_coordinator.run()),
        ]

        if self._audio_turn_consumer:
            self._consumer_tasks.append(
                asyncio.create_task(self._audio_turn_consumer.run())
            )

        self._output_task = asyncio.create_task(self._output_audio_loop())

        self._set_agent_state("listening")

    def _set_agent_state(self, state: str) -> None:
        """
        Update agent state and publish it to the LiveKit room as a participant
        attribute so the frontend (e.g. playground) reflects the correct state.

        LiveKit reads 'lk.agent.state' from the local participant's attributes
        to drive its UI indicators (initializing / listening / thinking / speaking).

        Publishing is skipped silently when the room is not yet connected
        (start() is called before ctx.connect()); the pending state will be
        flushed by _on_room_connected() once the connection is established.
        """
        self._agent_state = state  # type: ignore[assignment]
        if self._room and self._room.isconnected():
            asyncio.create_task(
                self._room.local_participant.set_attributes({"lk.agent.state": state})
            )

    def _on_room_connected(self) -> None:
        """
        Called when the room finishes connecting (the 'connected' event).
        Flushes the current agent state and publishes the pre-created audio track.
        """
        self._set_agent_state(self._agent_state)
        asyncio.create_task(self._publish_audio_track())

    async def _publish_audio_track(self) -> None:
        """Publish the pre-created audio track to the room."""
        if not self._audio_track or not self._room:
            return
        try:
            options = rtc.TrackPublishOptions(
                source=rtc.TrackSource.SOURCE_MICROPHONE,
            )
            await self._room.local_participant.publish_track(self._audio_track, options)
            logger.info(
                "agent audio track published (sample_rate=%d)",
                getattr(self._audio_source, "sample_rate", "?"),
            )
        except Exception:
            logger.exception("failed to publish agent audio track")

    def _start_track(self, track: rtc.Track) -> None:
        """
        Spawn a task to read frames from an audio track and push them to the
        input pipeline.  Keeps a strong reference so the task isn't GC'd.
        """
        if track.kind != rtc.TrackKind.KIND_AUDIO:
            return
        if track.sid in self._track_tasks:
            return  # already processing this track

        task = asyncio.create_task(
            self._process_audio_track(track),
            name=f"audio_track_{track.sid}",
        )
        self._track_tasks[track.sid] = task

        def _on_done(t: asyncio.Task) -> None:
            self._track_tasks.pop(track.sid, None)
            if not t.cancelled() and t.exception():
                logger.error(
                    "unhandled error in audio track processor",
                    exc_info=t.exception(),
                )

        task.add_done_callback(_on_done)

    def _setup_room_handlers(self) -> None:
        """
        Register LiveKit room event handlers so every remote audio track is
        forwarded to our processing pipeline.

        Called before ctx.connect() so the handlers are in place when the room
        fires 'track_subscribed' for the user's existing tracks.
        """
        if not self._room:
            return

        @self._room.on("connection_state_changed")
        def on_connection_state_changed(state: rtc.ConnectionState) -> None:
            if state == rtc.ConnectionState.CONN_CONNECTED:
                self._on_room_connected()

        @self._room.on("track_subscribed")
        def on_track_subscribed(
            track: rtc.Track,
            publication: rtc.RemoteTrackPublication,
            participant: rtc.RemoteParticipant,
        ) -> None:
            logger.debug(
                "track subscribed",
                extra={"participant": participant.identity, "kind": track.kind},
            )
            self._start_track(track)

        # Handle participants who are already in the room when start() is called
        # (rare before ctx.connect(), but safe to check).
        for participant in self._room.remote_participants.values():
            for publication in participant.track_publications.values():
                if publication.subscribed and publication.track:
                    self._start_track(publication.track)

    async def _process_audio_track(self, track: rtc.Track) -> None:
        """
        Stream audio frames from a subscribed remote track into the pipeline.

        Requests 16 kHz mono from LiveKit so Silero VAD and Deepgram STT both
        receive audio at the rate they expect without manual resampling.
        """
        audio_stream = rtc.AudioStream(
            track,
            sample_rate=16000,
            num_channels=1,
        )
        logger.debug("started reading audio stream for track %s", track.sid)
        try:
            async for event in audio_stream:
                if self._closed:
                    break
                await self._audio_pipeline.push_input_audio(event.frame)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("error reading audio stream for track %s", track.sid)
        finally:
            await audio_stream.aclose()
            logger.debug("stopped reading audio stream for track %s", track.sid)

    async def _evaluate_turn_complete(self) -> None:
        """
        Evaluate if turn is complete based on configured detectors.
        Implements turn decision logic with aggregation.
        Awaits generate_reply directly — use _evaluate_turn_complete_async to avoid
        blocking the caller.
        """
        config = self._config.turn_detection if self._config else None

        if not config or (
            not config.has_audio_detector() and not config.has_text_detector()
        ):
            await asyncio.sleep(config.min_endpointing_delay if config else 0.5)
            await self._trigger_turn_complete()
            return

        if config.has_audio_detector() and not config.has_text_detector():
            if self._audio_turn_probability >= config.audio_detector.threshold:
                await self._trigger_turn_complete()
            return

        if config.has_text_detector() and not config.has_audio_detector():
            if self._text_turn_probability >= config.text_detector.threshold:
                await self._trigger_turn_complete()
            return

        if config.needs_aggregation() and self._turn_aggregator:
            final_prob = self._turn_aggregator.aggregate(
                audio_prob=self._audio_turn_probability,
                text_prob=self._text_turn_probability,
            )

            if final_prob >= 0.5:
                await self._trigger_turn_complete()

    async def _evaluate_turn_complete_async(self) -> None:
        """
        Non-blocking version of _evaluate_turn_complete.

        Runs the endpointing delay + turn evaluation logic as a background task so
        the EventCoordinator is free to process new events (VAD, interruptions, etc.)
        while waiting for the delay and checking turn probabilities.

        If probability < threshold, waits up to max_endpointing_delay. During this window:
        - If user speaks again (VAD START_OF_SPEECH), this task is cancelled and restarted
        - If window expires without new speech, responds anyway

        Only one reply task runs at a time; if a reply is already in progress the new
        request is dropped (the running reply already incorporates the latest transcript).
        """
        # Capture transcript snapshot now; it may be mutated later by more STT events
        transcript_snapshot = self._current_transcript

        async def _run() -> None:
            td_config = self._config.turn_detection if self._config else None
            min_delay = td_config.min_endpointing_delay if td_config else 0.5
            max_delay = td_config.max_endpointing_delay if td_config else 3.0

            has_audio = self._audio_turn_detector is not None
            has_text = self._text_turn_detector is not None

            try:
                # Wait for minimum endpointing delay
                await asyncio.sleep(min_delay)

                logger.debug(
                    "turn evaluation: checking probabilities (audio=%.3f, text=%.3f, has_audio=%s, has_text=%s)",
                    self._audio_turn_probability,
                    self._text_turn_probability,
                    has_audio,
                    has_text,
                )

                # No turn detectors configured — always respond
                if not has_audio and not has_text:
                    logger.info("turn evaluation: no detectors configured, responding")
                    await self._trigger_turn_complete()
                    return

                # Determine threshold and probability based on detector configuration
                should_respond_immediately = False

                if has_audio and not has_text:
                    # Audio-only detector
                    audio_threshold = (
                        td_config.audio_detector.threshold
                        if td_config and td_config.audio_detector
                        else 0.5
                    )
                    should_respond_immediately = (
                        self._audio_turn_probability >= audio_threshold
                    )

                elif has_text and not has_audio:
                    # Text-only detector
                    text_threshold = getattr(
                        self._text_turn_detector, "_threshold", 0.5
                    )
                    should_respond_immediately = (
                        self._text_turn_probability >= text_threshold
                    )

                elif has_audio and has_text and self._turn_aggregator:
                    # Both detectors — aggregation
                    final_prob = self._turn_aggregator.aggregate(
                        audio_prob=self._audio_turn_probability,
                        text_prob=self._text_turn_probability,
                    )
                    should_respond_immediately = final_prob >= 0.5

                # If probability meets threshold, respond immediately
                if should_respond_immediately:
                    if has_audio and not has_text:
                        logger.info(
                            "turn complete: audio probability %.3f >= threshold %.3f",
                            self._audio_turn_probability,
                            td_config.audio_detector.threshold
                            if td_config and td_config.audio_detector
                            else 0.5,
                        )
                    elif has_text and not has_audio:
                        logger.info(
                            "turn complete: text probability %.3f >= threshold %.3f",
                            self._text_turn_probability,
                            getattr(self._text_turn_detector, "_threshold", 0.5),
                        )
                    elif has_audio and has_text:
                        logger.info(
                            "turn complete: aggregated probability %.3f >= 0.5 (audio=%.3f, text=%.3f)",
                            final_prob,
                            self._audio_turn_probability,
                            self._text_turn_probability,
                        )
                    await self._trigger_turn_complete()
                    return

                # Probability below threshold — wait up to max_endpointing_delay
                # During this window, if user speaks again, this task will be cancelled
                # and restarted by the new VAD END_OF_SPEECH event
                remaining_delay = max_delay - min_delay
                logger.info(
                    "turn incomplete: probability below threshold, waiting up to %.2fs for more speech",
                    remaining_delay,
                )

                await asyncio.sleep(remaining_delay)

                # Max delay expired without new speech — respond anyway
                logger.info(
                    "turn complete: max endpointing delay expired (%.2fs), responding anyway",
                    max_delay,
                )
                await self._trigger_turn_complete()

            except asyncio.CancelledError:
                logger.debug("turn evaluation: cancelled (likely due to new speech)")
                raise
            except Exception:
                logger.exception("generate_reply background task raised an error")
            finally:
                self._reply_task = None

        # If a reply task is already running, cancel it (new speech detected)
        if self._reply_task and not self._reply_task.done():
            logger.debug(
                "turn evaluation: cancelling previous evaluation (new speech detected, transcript=%r)",
                transcript_snapshot,
            )
            self._reply_task.cancel()
            try:
                await self._reply_task
            except asyncio.CancelledError:
                pass

        logger.debug(
            "EventCoordinator: scheduling generate_reply (transcript=%r)",
            transcript_snapshot,
        )
        self._reply_task = asyncio.create_task(_run(), name="generate_reply")

    async def _trigger_turn_complete(self) -> None:
        """Trigger turn complete event and generate response."""
        if self._current_transcript:
            self._conversation_context.add_turn(
                role="user", content=self._current_transcript
            )

        await self._event_bus.put(
            Event(
                type=EventType.TURN_COMPLETE,
                data=TurnCompleteData(
                    transcript=self._current_transcript,
                    audio_prob=self._audio_turn_probability,
                    text_prob=self._text_turn_probability,
                ),
            )
        )

        await self.generate_reply()

        self._current_transcript = ""
        self._audio_turn_probability = 0.0
        self._text_turn_probability = 0.0

    async def _output_audio_loop(self) -> None:
        """
        Output audio loop — captures synthesized audio frames to the LiveKit room.

        The AudioSource and LocalAudioTrack are created in start() and published
        as soon as the room connects (_on_room_connected → _publish_audio_track).

        Uses AudioByteStream to buffer and rebatch audio frames into consistent sizes,
        preventing InvalidState errors that occur when frames arrive too quickly.
        This matches LiveKit's approach in their TTS plugins.
        """
        frames_captured = 0
        current_utterance_frames = 0  # Track frames for current utterance

        try:
            async for audio_frame in self._audio_pipeline.output_stream():
                if self._closed:
                    break

                if self._audio_source is None:
                    # Source not ready yet (room not connected) — skip silently.
                    continue

                # Initialize AudioByteStream on first frame to match sample rate
                if self._audio_bstream is None:
                    # Buffer frames to 200ms chunks to prevent InvalidState errors
                    samples_per_channel = audio_frame.sample_rate // 5  # 200ms
                    self._audio_bstream = audio_utils.AudioByteStream(
                        sample_rate=audio_frame.sample_rate,
                        num_channels=audio_frame.num_channels,
                        samples_per_channel=samples_per_channel,
                    )
                    logger.debug(
                        "initialized AudioByteStream (sample_rate=%d, chunk_size=%d samples = 200ms)",
                        audio_frame.sample_rate,
                        samples_per_channel,
                    )

                # Check for interruption before processing frame
                if self._interruption_handler.is_interrupted:
                    logger.info(
                        "output loop: interruption detected, stopping audio capture (frames_captured=%d)",
                        frames_captured,
                    )
                    break

                # Push frame data into buffer and get rebatched frames
                rebatched_frames = self._audio_bstream.push(audio_frame.data.tobytes())

                # Capture each rebatched frame
                for frame in rebatched_frames:
                    # Check for interruption before each frame capture
                    if self._interruption_handler.is_interrupted:
                        logger.info(
                            "output loop: interruption detected during frame capture, stopping (frames_captured=%d)",
                            frames_captured,
                        )
                        break

                    try:
                        await self._audio_source.capture_frame(frame)
                        frames_captured += 1
                        current_utterance_frames += 1

                        if frames_captured == 1 or current_utterance_frames == 1:
                            # First frame of this utterance - agent is now actually speaking
                            if not self._audio_publishing:
                                self._audio_publishing = True
                                self._set_agent_state("speaking")
                                logger.info(
                                    "first audio frame captured to source "
                                    "(sample_rate=%d, samples=%d, duration=%.3fs)",
                                    frame.sample_rate,
                                    frame.samples_per_channel,
                                    frame.duration,
                                )
                        elif frames_captured % 50 == 0:
                            logger.debug(
                                "audio output: %d frames captured so far",
                                frames_captured,
                            )
                    except Exception as e:
                        if "InvalidState" in str(e):
                            logger.warning(
                                "capture_frame InvalidState on frame %d (room_connected=%s)",
                                frames_captured,
                                self._room.isconnected(),
                            )
                            if not self._room.isconnected():
                                logger.info("room disconnected, stopping output loop")
                                return
                            # Skip this frame and continue
                            continue
                        else:
                            logger.exception(
                                "capture_frame failed on frame %d — stopping output loop",
                                frames_captured,
                            )
                            return

                # Break outer loop if interrupted during inner loop
                if self._interruption_handler.is_interrupted:
                    break
                
                # Check if generation is complete and queue might be empty
                if self._generation_complete.is_set() and current_utterance_frames > 0:
                    # Wait a bit to see if more frames arrive
                    await asyncio.sleep(0.05)
                    # If queue is empty, this utterance is done
                    if self._audio_pipeline._output_queue.empty():
                        logger.info(
                            "utterance complete: %d frames published",
                            current_utterance_frames,
                        )
                        current_utterance_frames = 0
                        self._audio_publishing = False
                        self._set_agent_state("listening")

        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("unexpected error in output audio loop")
        finally:
            # Flush any remaining buffered audio (unless interrupted)
            if (
                self._audio_bstream is not None
                and not self._interruption_handler.is_interrupted
            ):
                try:
                    remaining_frames = self._audio_bstream.flush()
                    for frame in remaining_frames:
                        if self._audio_source and self._room.isconnected():
                            try:
                                await self._audio_source.capture_frame(frame)
                                frames_captured += 1
                            except Exception:
                                pass
                except Exception:
                    pass
            
            # Ensure state is reset when loop exits
            if self._audio_publishing:
                self._audio_publishing = False
                self._set_agent_state("listening")
                logger.info("audio publishing stopped, state reset to listening")

            logger.debug(
                "output audio loop exited (%d frames captured)", frames_captured
            )
            if self._audio_track and self._room:
                try:
                    await self._room.local_participant.unpublish_track(
                        self._audio_track.sid
                    )
                except Exception:
                    pass
            if self._audio_source:
                await self._audio_source.aclose()
                self._audio_source = None

    async def _handle_interruption(self) -> None:
        """Handle user interruption - cancel ongoing reply task."""
        logger.info("_handle_interruption: cancelling reply task")
        await self._interruption_handler.interrupt()

        # Cancel the active reply task if it's running
        if self._reply_task and not self._reply_task.done():
            self._reply_task.cancel()
            try:
                await self._reply_task
            except asyncio.CancelledError:
                pass
            self._reply_task = None

        # Drain any queued audio frames to stop playback immediately
        logger.debug("_handle_interruption: draining output audio queue and buffer")
        self._audio_pipeline.clear_buffers()

        # Clear the AudioByteStream buffer to stop any buffered audio
        if self._audio_bstream is not None:
            self._audio_bstream.clear()
            logger.debug("_handle_interruption: cleared AudioByteStream buffer")

        # Reset transcript accumulation
        self._current_transcript = ""
        self._audio_turn_probability = 0.0
        self._text_turn_probability = 0.0

        self._set_agent_state("listening")

    async def say(self, text: str) -> None:
        """
        Make the agent speak text.

        Args:
            text: Text to speak
        """
        if self._closed:
            return

        self._generation_complete.clear()  # Mark generation as in progress
        self._interruption_handler.set_agent_speaking(True)

        try:
            async for audio_frame in self._tts.synthesize_stream(text):
                if self._interruption_handler.is_interrupted:
                    break

                await self._audio_pipeline.push_output_audio(audio_frame)

            self._conversation_context.add_turn(
                role="assistant",
                content=text,
            )

        finally:
            self._generation_complete.set()  # Mark generation as complete
            self._interruption_handler.set_agent_speaking(False)
            # Reset interruption state for next turn
            self._interruption_handler.reset()

    async def generate_reply(self, user_input: str | None = None) -> None:
        """
        Generate and speak LLM response with streaming.

        LLM returns async iterator that is fed directly to TTS.
        TTS handles internal chunking based on its configured strategy.

        Args:
            user_input: Optional user input to respond to
        """
        if self._closed:
            return

        if user_input:
            self._conversation_context.add_turn(
                role="user",
                content=user_input,
            )

        self._set_agent_state("thinking")
        self._generation_complete.clear()  # Mark generation as in progress
        self._interruption_handler.set_agent_speaking(True)

        try:
            messages = self._conversation_context.to_llm_messages()
            logger.info(
                "generate_reply: starting LLM→TTS pipeline (history=%d turns, user_input=%r)",
                len(messages),
                user_input,
            )

            # Tee the LLM token stream: collect text AND forward to TTS simultaneously
            # so conversation history is populated without adding latency.
            collected_tokens: list[str] = []

            async def _collecting_token_stream() -> AsyncIterable[str]:
                token_idx = 0
                async for token in self._llm.generate_stream(messages):
                    token_idx += 1
                    if token_idx == 1:
                        logger.debug(
                            "generate_reply: first token from LLM: %r", token[:20]
                        )
                    collected_tokens.append(token)
                    yield token
                logger.debug(
                    "generate_reply: LLM stream complete (%d tokens collected)",
                    token_idx,
                )

            frames_pushed = 0

            try:
                async for audio_frame in self._tts.synthesize_stream_from_iterator(
                    _collecting_token_stream()
                ):
                    if self._interruption_handler.is_interrupted:
                        logger.info(
                            "generate_reply: interrupted after %d frames", frames_pushed
                        )
                        break

                    await self._audio_pipeline.push_output_audio(audio_frame)
                    frames_pushed += 1
            except Exception:
                logger.exception("generate_reply: error in LLM→TTS pipeline")
                raise

            logger.info(
                "generate_reply: pipeline done (%d audio frames pushed, interrupted=%s, collected_tokens=%d)",
                frames_pushed,
                self._interruption_handler.is_interrupted,
                len(collected_tokens),
            )

            if not self._interruption_handler.is_interrupted:
                full_response = "".join(collected_tokens)
                self._conversation_context.add_turn(
                    role="assistant",
                    content=full_response,
                )

        finally:
            self._generation_complete.set()  # Mark generation as complete
            self._interruption_handler.set_agent_speaking(False)
            # Reset interruption state for next turn
            self._interruption_handler.reset()

    async def aclose(self) -> None:
        """Close session and cancel all consumer tasks."""
        if self._closed:
            return

        self._closed = True

        self._audio_distributor.close()
        self._vad_consumer.close()
        self._stt_consumer.close()
        if self._audio_turn_consumer:
            self._audio_turn_consumer.close()
        self._event_coordinator.close()

        await self._event_bus.put(Event(type=EventType.SHUTDOWN, data=None))

        for task in list(self._track_tasks.values()):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._track_tasks.clear()

        for task in self._consumer_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        if self._reply_task and not self._reply_task.done():
            self._reply_task.cancel()
            try:
                await self._reply_task
            except asyncio.CancelledError:
                pass

        if self._output_task:
            self._output_task.cancel()
            try:
                await self._output_task
            except asyncio.CancelledError:
                pass

        await self._vad.aclose()
        await self._stt.close()
        await self._llm.close()
        await self._tts.close()
        await self._audio_pipeline.aclose()

    @property
    def user_state(self) -> str:
        """Get current user state."""
        return self._user_state

    @property
    def agent_state(self) -> str:
        """Get current agent state."""
        return self._agent_state

    @property
    def conversation_history(self) -> ConversationContext:
        """Get conversation history (including tool calls and results)."""
        return self._conversation_context

    def dump_transcript(self) -> list[dict]:
        """
        Return the full conversation transcript as a list of plain dicts.

        Each entry has at minimum: ``role``, ``content``, ``timestamp``.
        Tool-call entries also carry ``tool_calls``.
        Tool-result entries also carry ``tool_call_id``.

        Suitable for logging, JSON serialisation, or storing in a database.
        """
        return self._conversation_context.dump_transcript()

    def dump_transcript_json(self, indent: int = 2) -> str:
        """Return the full transcript as a formatted JSON string."""
        return self._conversation_context.dump_transcript_json(indent=indent)
