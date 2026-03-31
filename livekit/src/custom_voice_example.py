"""Example usage of the custom voice stack.

This demonstrates how to use the custom voice stack instead of LiveKit's AgentSession,
including per-agent prompts and tool calling.

Agent selection can be driven by LiveKit job metadata, e.g.:
    {"agent_name": "customer_support"}
"""

import json
import logging
import os
from pathlib import Path

import httpx
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
        try:
            metadata = json.loads(metadata)
        except Exception:
            metadata = {}

    # Extract session_id and config from metadata
    session_id = metadata.get("session_id")
    session_config = metadata.get("config", {})
    
    # Extract provider configurations with defaults
    llm_provider = session_config.get("llm_provider", "openai")
    llm_config = session_config.get("llm_config", {})
    stt_provider = session_config.get("stt_provider", "assemblyai")
    stt_config = session_config.get("stt_config", {})
    tts_provider = session_config.get("tts_provider", "cartesia")
    tts_config = session_config.get("tts_config", {})
    agent_name = session_config.get("agent_name", "general_assistant")
    
    logger.info(
        "Loading agent %r (session_id=%s, llm=%s, stt=%s, tts=%s)",
        agent_name,
        session_id,
        llm_provider,
        stt_provider,
        tts_provider,
    )
    agent = create_agent(agent_name)

    # ----------------------------------------------------------------
    # Create STT with dynamic configuration
    # ----------------------------------------------------------------
    logger.info("Creating STT: provider=%s, config=%s", stt_provider, stt_config)
    stt = create_stt(provider=stt_provider, **stt_config)

    # ----------------------------------------------------------------
    # Create LLM with dynamic configuration
    # ----------------------------------------------------------------
    logger.info("Creating LLM: provider=%s, config=%s", llm_provider, llm_config)
    llm = create_llm(
        provider=llm_provider,
        tools=agent.tools,  # bind tools to model
        tool_handler=agent.make_tool_handler(),  # execute on call
        **llm_config,
    )

    # ----------------------------------------------------------------
    # Create TTS with dynamic configuration
    # ----------------------------------------------------------------
    logger.info("Creating TTS: provider=%s, config=%s", tts_provider, tts_config)
    tts = create_tts(provider=tts_provider, **tts_config)

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
    @ctx.room.on("participant_disconnected")
    def _on_disconnected(*_args):
        transcript = session.dump_transcript()
        logger.info(
            "=== CALL TRANSCRIPT (session=%s, %d turns) ===\n%s",
            session_id,
            len(transcript),
            session.dump_transcript_json(),
        )
        
        # Send transcript to API using session_id
        if session_id:
            import asyncio
            asyncio.create_task(_update_session_transcript(session_id, transcript))
        else:
            logger.warning("No session_id in metadata, transcript not sent to API")
    
    async def _update_session_transcript(session_id: str, transcript: list[dict]) -> None:
        """Update session with transcript via API."""
        try:
            base_url = os.getenv("API_BASE_URL")
            if not base_url:
                logger.error("API_BASE_URL not set in environment, cannot send transcript")
                return
            
            # Remove trailing slash if present
            base_url = base_url.rstrip("/")
            
            # Prepare the request body
            payload = {
                "transcript": transcript
            }
            
            url = f"{base_url}/sessions/{session_id}"
            
            logger.info(
                "Sending transcript to API: PATCH %s (%d turns)",
                url,
                len(transcript),
            )
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.patch(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                
                if response.status_code == 200:
                    logger.info(
                        "Transcript successfully sent to API for session %s",
                        session_id,
                    )
                else:
                    logger.error(
                        "Failed to send transcript to API: status=%d, response=%s",
                        response.status_code,
                        response.text,
                    )
        except Exception as e:
            logger.error("Error sending transcript to API: %s", e, exc_info=True)


if __name__ == "__main__":
    cli.run_app(server)
