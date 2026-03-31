"""Example using ElevenLabs TTS with custom voice stack."""

import logging

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentServer,
    JobContext,
    JobProcess,
    cli,
)

from custom_voice import (
    CustomAgentSession,
    create_llm,
    create_stt,
    create_tts,
    create_vad,
)
from custom_voice.tts import ChunkingStrategy

logger = logging.getLogger("elevenlabs-agent")

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
    pass


server.setup_fnc = prewarm


@server.rtc_session(agent_name="elevenlabs-voice-stack")
async def my_agent(ctx: JobContext):
    """Agent using custom voice stack with ElevenLabs TTS."""
    
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }
    
    logger.info("Creating custom voice stack with ElevenLabs TTS...")
    
    stt = create_stt(
        provider="deepgram",
        model="nova-3",
        language="multi",
        transport="websocket",
    )
    
    llm = create_llm(
        provider="openai",
        model="gpt-4.1-mini",
        temperature=0.7,
    )
    
    tts = create_tts(
        provider="elevenlabs",
        voice="l7kNoIfnJKPg7779LI2t",
        model="eleven_turbo_v2_5",
        chunking_strategy=ChunkingStrategy.SENTENCE,
        min_chunk_size=10,
        auto_mode=True,
    )
    
    vad = create_vad(
        provider="silero",
        threshold=0.5,
    )
    
    logger.info("Creating custom agent session...")
    
    session = CustomAgentSession(
        stt=stt,
        llm=llm,
        tts=tts,
        vad=vad,
    )
    
    logger.info("Starting custom agent session...")
    
    await session.start(
        room=ctx.room,
        instructions="help the user with their questions and requests"
    )
    
    await ctx.connect()
    
    logger.info("ElevenLabs voice stack agent is running!")


if __name__ == "__main__":
    cli.run_app(server)
