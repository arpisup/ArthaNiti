from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AnalysisContext:
    """Shared context passed to all agents for a single assessment run.

    This object carries the user's request (policy inputs, profile,
    time horizon) alongside runtime references to the simulation engine,
    knowledge index, and scheme database. Each agent reads from this
    context to perform its specialized analysis.

    The context is constructed once per assessment and is immutable from
    the agents' perspective — agents produce results, they do not mutate
    the context.
    """

    # User request parameters
    policy_inputs: dict[str, Any] | None = None
    horizon_years: int | None = None
    user_profile: dict[str, Any] | None = None
    user_query: str | None = None

    # Runtime references (set by the Orchestrator at construction time)
    engine: Any = None
    knowledge_index: Any = None
    schemes: list[Any] = field(default_factory=list)
    snapshot: dict[str, Any] = field(default_factory=dict)
    base_dir: Path | None = None

    # Intermediate results from other agents (populated by Orchestrator)
    simulation_result: dict[str, Any] | None = None
    persona_weights: dict[str, float] | None = None


class BaseAgent(ABC):
    """Abstract base class for all specialized agents.

    Each agent receives an AnalysisContext and returns a dict of results.
    Agents are designed to be:
    - Independent: no direct dependencies on other agents
    - Deterministic: same context produces same results
    - Composable: the Orchestrator can run them in any order
    - Testable: each agent can be tested in isolation

    The Orchestrator may enrich the context with intermediate results
    from previously-run agents (e.g., simulation_result) before
    invoking agents that depend on those results.
    """

    @property
    @abstractmethod
    def agent_id(self) -> str:
        """Unique identifier for this agent type."""

    @property
    @abstractmethod
    def agent_name(self) -> str:
        """Human-readable name for this agent."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Brief description of what this agent does."""

    @abstractmethod
    def analyze(self, context: AnalysisContext) -> dict[str, Any]:
        """Perform the agent's specialized analysis.

        Args:
            context: Shared analysis context with request parameters
                     and runtime references.

        Returns:
            A dict containing the agent's analysis results.
            The exact structure depends on the agent type.
        """

    def agent_metadata(self) -> dict[str, str]:
        """Return metadata about this agent for API responses."""
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "description": self.description,
        }
