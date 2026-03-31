"""Agent factory.

Maps agent names to their classes. Add new agents here.

Usage
-----
    from custom_voice.agent import create_agent

    agent = create_agent("customer_support")
    print(agent.instructions)
    print(agent.get_tool_definitions())
"""

from __future__ import annotations

from .agents import CustomerSupportAgent, GeneralAssistantAgent
from .base import BaseAgent

# Registry: name -> class (not instance, so each call gets a fresh agent)
_REGISTRY: dict[str, type[BaseAgent]] = {
    GeneralAssistantAgent.name: GeneralAssistantAgent,
    CustomerSupportAgent.name: CustomerSupportAgent,
}


def create_agent(name: str) -> BaseAgent:
    """
    Create an agent by name.

    Args:
        name: Agent name as registered in the registry
              (e.g. "general_assistant", "customer_support").

    Returns:
        A fresh BaseAgent instance.

    Raises:
        ValueError: If the name is not registered.
    """
    cls = _REGISTRY.get(name)
    if cls is None:
        available = ", ".join(sorted(_REGISTRY))
        raise ValueError(
            f"Unknown agent {name!r}. Available agents: {available}"
        )
    return cls()


def list_agents() -> list[str]:
    """Return all registered agent names."""
    return sorted(_REGISTRY)
