"""Concrete agent definitions.

Add new agents here and register them in factory.py.
Each agent has its own system prompt and tool set.
"""

from __future__ import annotations

import logging
from random import random
from typing import Annotated

from langchain_core.tools import BaseTool, tool

from .base import BaseAgent

logger = logging.getLogger("custom-agent")


# ============================================================================
# General Assistant
# ============================================================================

@tool
async def get_current_time() -> str:
    """Get the current date and time."""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@tool
async def get_weather(
    location: Annotated[str, "City name or location (e.g. 'Bangalore, India')"],
) -> str:
    """Get the current weather for a location."""
    # Stub — replace with a real weather API call
    logger.info("get_weather called for location=%r", location)
    return f"The weather in {location} is currently sunny with a temperature of 72°F."


class GeneralAssistantAgent(BaseAgent):
    """
    A general-purpose voice assistant.

    Good for everyday Q&A, time queries, and weather lookups.
    """

    name = "general_assistant"
    instructions = (
        "You are a helpful voice AI assistant. "
        "The user is speaking to you — keep responses concise and conversational. "
        "Avoid markdown, bullet points, emojis, or any formatting. "
        "Speak in plain, friendly sentences."
    )

    @property
    def tools(self) -> list[BaseTool]:
        return [get_current_time, get_weather]


# ============================================================================
# Customer Support Agent
# ============================================================================

@tool
async def lookup_order(
    order_id: Annotated[str, "The order ID to look up (e.g. 'ORD-12345')"],
) -> str:
    """Look up the status of an order by its order ID."""
    logger.info("lookup_order called for order_id=%r", order_id)
    # Stub — replace with a real database/API call
    return (
        f"Order {order_id} is currently in transit and expected to arrive "
        f"within 2 business days."
    )


@tool
async def cancel_order(
    order_id: Annotated[str, "The order ID to cancel"],
    reason: Annotated[str, "Reason for cancellation"] = "Customer request",
) -> str:
    """Cancel an existing order."""
    logger.info("cancel_order called for order_id=%r reason=%r", order_id, reason)
    # Stub — replace with a real cancellation API call
    return (
        f"Order {order_id} has been successfully cancelled. "
        "You will receive a confirmation email shortly."
    )


@tool
async def get_return_policy() -> str:
    """Get the company's return and refund policy."""
    return (
        "Our return policy allows returns within 30 days of purchase for a full refund. "
        "Items must be in original condition with packaging. "
        "Refunds are processed within 5 to 7 business days."
    )


class CustomerSupportAgent(BaseAgent):
    """
    A customer support voice agent.

    Handles order lookups, cancellations, and policy questions.
    """

    name = "customer_support"
    instructions = (
        "You are a friendly customer support representative. "
        "Help customers with their orders, returns, and general inquiries. "
        "Always be empathetic and professional. "
        "Keep responses brief and clear — the customer is speaking to you by voice. "
        "Do not use markdown or special formatting."
    )

    @property
    def tools(self) -> list[BaseTool]:
        return [lookup_order, cancel_order, get_return_policy]
