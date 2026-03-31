"""Example usage of the custom voice stack.

This demonstrates how to use the custom voice stack instead of LiveKit's AgentSession,
including per-agent prompts and tool calling.

Agent selection can be driven by LiveKit job metadata, e.g.:
    {"agent_name": "customer_support"}
"""

import logging

from dotenv import load_dotenv
from livekit.agents import (
    AgentServer,
    JobContext,
    JobProcess,
    cli,
)

# Custom voice stack
from custom_voice import (
    CustomAgentSession,
    create_llm,
    create_stt,
    create_tts,
    create_vad,
)
from custom_voice.agent import create_agent
from custom_voice.turn_detection.factory import create_turn_detector

logger = logging.getLogger("custom-agent")

load_dotenv(".env.local")

server = AgentServer()


def prewarm(proc: JobProcess) -> None:
    pass


server.setup_fnc = prewarm


@server.rtc_session(agent_name="custom-voice-stack")
async def my_agent(ctx: JobContext) -> None:
    """Voice agent with per-agent prompts and tool calling."""

    ctx.log_context_fields = {"room": ctx.room.name}

    # ----------------------------------------------------------------
    # Pick agent from job metadata (default: general_assistant)
    # ----------------------------------------------------------------
    metadata = ctx.job.metadata if ctx.job and ctx.job.metadata else {}
    if isinstance(metadata, str):
        import json

        try:
            metadata = json.loads(metadata)
        except Exception:
            metadata = {}

    agent_name = metadata.get("agent_name", "general_assistant")
    logger.info("Loading agent %r", agent_name)
    agent = create_agent(agent_name)

    # ----------------------------------------------------------------
    # STT
    # ----------------------------------------------------------------
    stt = create_stt(
        provider="assemblyai",
        # provider="deepgram",
        # model="nova-3",
        # language="multi",
        # transport="websocket",
    )

    llm = create_llm(
        provider="openai",
        model="gpt-4.1-mini",
        temperature=0.7,
        tools=agent.tools,  # bind tools to model
        tool_handler=agent.make_tool_handler(),  # execute on call
    )

    # # Option 1: ElevenLabs TTS
    # tts = create_tts(
    #     provider="elevenlabs",
    #     model="eleven_flash_v2_5",
    #     voice="hpp4J3VqNfWAUOO0d1Us",  # Default voice
    #     transport="http",  # HTTP streaming is more reliable for per-utterance synthesis
    # )

    # Option 2: Cartesia TTS
    tts = create_tts(
        provider="cartesia",
        model="sonic-3",
        voice="9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",  # Example voice ID
        transport="http",
    )

    # Option 2: ElevenLabs TTS (uncomment to use)
    # tts = create_tts(
    #     provider="elevenlabs",
    #     voice_id="l7kNoIfnJKPg7779LI2t",  # Default voice
    #     model="eleven_turbo_v2_5",
    #     chunking_strategy=ChunkingStrategy.SENTENCE,
    # )

    vad = create_vad(
        provider="silero",
        threshold=0.5,
    )

    # Optional: Create turn detectors
    # Uncomment to enable turn detection

    # audio_turn_detector = create_turn_detector(
    #     "vad",
    #     silence_duration=0.8,
    #     threshold=0.5,
    # )

    # Option 1: Simple rule-based EOU turn detector
    # text_turn_detector = create_turn_detector(
    #     "eou",
    #     context_window_turns=4,
    #     threshold=0.7,
    # )

    # Option 2: LiveKit ML-based EOU turn detector (recommended)
    # Uses the official LiveKit turn detection model (99.3% accuracy)
    # Requires model weights to be downloaded first: uv run src/custom_voice_example.py download-files
    text_turn_detector = create_turn_detector(
        "livekit_eou",
        context_window_turns=6,
        threshold=0.5,
    )

    logger.info("Creating custom agent session...")

    # Create custom agent session
    session = CustomAgentSession(
        stt=stt,
        llm=llm,
        tts=tts,
        vad=vad,
        # audio_turn_detector=audio_turn_detector,  # Uncomment if using
        text_turn_detector=text_turn_detector,  # Uncomment if using
    )

    await session.start(
        room=ctx.room,
        instructions=agent.instructions,
    )

    await ctx.connect()

    logger.info(
        "Agent %r is running (tools: %s)",
        agent.name,
        [t.name for t in agent.tools],
    )

    # Wait for the room to disconnect, then dump the full transcript.
    # ctx.connect() returns once the room is connected; the job stays alive
    # until the LiveKit worker framework decides to shut it down.
    # We register a disconnect handler to capture the transcript.
    @ctx.room.on("disconnected")
    def _on_disconnected(*_args):
        transcript = session.dump_transcript()
        logger.info(
            "=== CALL TRANSCRIPT (%d turns) ===\n%s",
            len(transcript),
            session.dump_transcript_json(),
        )
        # TODO: persist transcript to a database or analytics service here


if __name__ == "__main__":
    cli.run_app(server)
