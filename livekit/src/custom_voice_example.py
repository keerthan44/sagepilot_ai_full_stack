"""Example usage of the custom voice stack.

This demonstrates how to use the custom voice stack instead of LiveKit's AgentSession.
"""

import logging

from custom_voice.turn_detection.factory import create_turn_detector
from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    JobContext,
    JobProcess,
    cli,
)

# Import custom voice stack
from custom_voice import (
    AudioTurnDetectorConfig,
    CustomAgentSession,
    TextTurnDetectorConfig,
    TurnDetectionConfig,
    create_llm,
    create_stt,
    create_tts,
    create_vad,
)
from custom_voice.tts import ChunkingStrategy

logger = logging.getLogger("custom-agent")

load_dotenv(".env.local")


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""You are a helpful voice AI assistant. The user is interacting with you via voice.
            You eagerly assist users with their questions by providing information from your extensive knowledge.
            Your responses are concise, to the point, and without any complex formatting or punctuation including emojis, asterisks, or other symbols.
            You are curious, friendly, and have a sense of humor.""",
        )


server = AgentServer()


def prewarm(proc: JobProcess):
    """Prewarm models and components."""
    # Note: In the custom stack, we don't use the prewarm pattern
    # Components are initialized when the session is created
    pass


server.setup_fnc = prewarm


@server.rtc_session(agent_name="custom-voice-stack")
async def my_agent(ctx: JobContext):
    """Agent using custom voice stack."""
    
    # Logging setup
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }
    
    logger.info("Creating custom voice stack components...")
    
    # Create components using factory functions
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
    )
    
    # Option 1: ElevenLabs TTS
    tts = create_tts(
        provider="elevenlabs",
        model="eleven_flash_v2_5",
        voice="hpp4J3VqNfWAUOO0d1Us",  # Default voice
        transport="http",  # HTTP streaming is more reliable for per-utterance synthesis
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
        text_turn_detector=text_turn_detector,    # Uncomment if using
    )
    
    logger.info("Starting custom agent session...")
    
    # Start the session first — registers room handlers before the room connects,
    # so no track_subscribed events are missed (same pattern as LiveKit's AgentSession).
    await session.start(
        room=ctx.room,
        instructions="help the user with their questions and requests"
    )
    
    # Connect to the room — fires track/participant events into already-registered handlers.
    # The LiveKit worker framework keeps the job alive until the room disconnects.
    await ctx.connect()
    
    logger.info("Custom voice stack agent is running!")


if __name__ == "__main__":
    cli.run_app(server)
