"""Tests for LiveKit EOU turn detector.

Note: Most tests are skipped because the LiveKit model requires a job context
(InferenceExecutor) which is only available inside a LiveKit agent job.
The model is tested indirectly through integration tests that run the full agent.
"""

import time

import pytest

from custom_voice.protocols import ConversationTurn
from custom_voice.turn_detection.livekit_eou import LiveKitEOUTurnDetector


@pytest.fixture
def detector():
    """Create a LiveKit EOU turn detector instance."""
    return LiveKitEOUTurnDetector(
        threshold=0.5,
        context_window_turns=4,
    )


def test_initialization(detector):
    """Test that the detector initializes correctly."""
    assert detector is not None
    assert detector.threshold == 0.5
    assert detector.context_window_turns == 4
    # Model is lazily initialized, so it's None until first use
    assert detector._model is None


def test_empty_transcript_returns_zero(detector):
    """Test that empty transcripts return 0.0 probability without calling model."""
    import asyncio
    prob = asyncio.run(detector.process_transcript(
        transcript="",
        is_final=True,
        conversation_context=[],
    ))
    assert prob == 0.0
    # Model should not be initialized for empty transcript
    assert detector._model is None


def test_interim_transcript_ignored(detector):
    """Test that interim transcripts are ignored without calling model."""
    import asyncio
    prob = asyncio.run(detector.process_transcript(
        transcript="Hello there",
        is_final=False,
        conversation_context=[],
    ))
    assert prob == 0.0
    # Model should not be initialized for interim transcript
    assert detector._model is None


# The following tests require a LiveKit job context and are skipped in unit tests.
# They are tested indirectly through integration tests that run the full agent.

@pytest.mark.skip(reason="Requires LiveKit job context (InferenceExecutor)")
@pytest.mark.asyncio
async def test_simple_question(detector):
    """Test turn detection for a simple question."""
    conversation_context = [
        ConversationTurn(role="assistant", content="Hi! How can I help you today?"),
    ]
    
    prob = await detector.process_transcript(
        transcript="What's the weather like?",
        is_final=True,
        conversation_context=conversation_context,
    )
    
    assert 0.0 <= prob <= 1.0
    assert prob > 0.3


@pytest.mark.skip(reason="Requires LiveKit job context (InferenceExecutor)")
@pytest.mark.asyncio
async def test_incomplete_utterance(detector):
    """Test turn detection for an incomplete utterance."""
    conversation_context = [
        ConversationTurn(role="assistant", content="What would you like to know?"),
    ]
    
    prob = await detector.process_transcript(
        transcript="I need to think about",
        is_final=True,
        conversation_context=conversation_context,
    )
    
    assert 0.0 <= prob <= 1.0


@pytest.mark.skip(reason="Requires LiveKit job context (InferenceExecutor)")
@pytest.mark.asyncio
async def test_with_conversation_context(detector):
    """Test turn detection with conversation history."""
    conversation_context = [
        ConversationTurn(role="assistant", content="Hello! I'm your AI assistant."),
        ConversationTurn(role="user", content="Hi there!"),
        ConversationTurn(role="assistant", content="How can I help you today?"),
    ]
    
    prob = await detector.process_transcript(
        transcript="I need help with my account.",
        is_final=True,
        conversation_context=conversation_context,
    )
    
    assert 0.0 <= prob <= 1.0


def test_chat_context_building(detector):
    """Test that chat context is built correctly."""
    now = time.time()
    conversation_context = [
        ConversationTurn(role="system", content="You are a helpful assistant.", timestamp=now),
        ConversationTurn(role="user", content="Hello", timestamp=now + 1),
        ConversationTurn(role="assistant", content="Hi there!", timestamp=now + 2),
    ]
    
    chat_ctx = detector._build_chat_context("How are you?", conversation_context)
    
    # Should have user + assistant + current user message
    # (system messages are skipped)
    messages = list(chat_ctx.messages())
    assert len(messages) == 3
    assert messages[0].role == "user"
    assert messages[0].text_content == "Hello"
    assert messages[1].role == "assistant"
    assert messages[1].text_content == "Hi there!"
    assert messages[2].role == "user"
    assert messages[2].text_content == "How are you?"


def test_context_window_limit(detector):
    """Test that context window is properly limited."""
    # Create 10 turns (more than the 4-turn window)
    now = time.time()
    conversation_context = []
    for i in range(10):
        conversation_context.append(
            ConversationTurn(role="user", content=f"Message {i}", timestamp=now + i * 2)
        )
        conversation_context.append(
            ConversationTurn(role="assistant", content=f"Response {i}", timestamp=now + i * 2 + 1)
        )
    
    chat_ctx = detector._build_chat_context("Final message", conversation_context)
    messages = list(chat_ctx.messages())
    
    # Should have at most context_window_turns + 1 (current message)
    # With 4 turns = 4 messages (2 user, 2 assistant) + 1 current = 5 total
    assert len(messages) <= detector.context_window_turns + 1


def test_system_messages_filtered(detector):
    """Test that system messages are filtered from context."""
    now = time.time()
    conversation_context = [
        ConversationTurn(role="system", content="You are a helpful assistant.", timestamp=now),
        ConversationTurn(role="system", content="Be concise.", timestamp=now + 1),
        ConversationTurn(role="user", content="Hello", timestamp=now + 2),
        ConversationTurn(role="assistant", content="Hi!", timestamp=now + 3),
    ]
    
    chat_ctx = detector._build_chat_context("Test", conversation_context)
    messages = list(chat_ctx.messages())
    
    # Should only have user and assistant messages, no system
    assert all(msg.role in ("user", "assistant") for msg in messages)
    assert len(messages) == 3  # user "Hello" + assistant "Hi!" + current "Test"


# The following tests require a LiveKit job context and are skipped in unit tests.
# They are tested through integration tests or manual testing with the full agent.

@pytest.mark.skip(reason="Requires LiveKit job context (InferenceExecutor)")
@pytest.mark.asyncio
async def test_error_handling_graceful_fallback(detector):
    """Test that errors are handled gracefully with fallback."""
    conversation_context = [
        ConversationTurn(role="user", content=""),
        ConversationTurn(role="assistant", content=""),
    ]
    
    prob = await detector.process_transcript(
        transcript="Test",
        is_final=True,
        conversation_context=conversation_context,
    )
    
    assert 0.0 <= prob <= 1.0


@pytest.mark.skip(reason="Requires LiveKit job context (InferenceExecutor)")
@pytest.mark.asyncio
async def test_complete_statement(detector):
    """Test detection of a complete statement."""
    conversation_context = [
        ConversationTurn(role="assistant", content="What can I do for you?"),
    ]
    
    prob = await detector.process_transcript(
        transcript="I would like to book a flight to New York.",
        is_final=True,
        conversation_context=conversation_context,
    )
    
    assert 0.0 <= prob <= 1.0
    assert prob > 0.2


@pytest.mark.skip(reason="Requires LiveKit job context (InferenceExecutor)")
@pytest.mark.asyncio
async def test_continuation_phrase(detector):
    """Test detection of a phrase that suggests continuation."""
    conversation_context = [
        ConversationTurn(role="assistant", content="Tell me more."),
    ]
    
    prob = await detector.process_transcript(
        transcript="Well, let me think",
        is_final=True,
        conversation_context=conversation_context,
    )
    
    assert 0.0 <= prob <= 1.0
