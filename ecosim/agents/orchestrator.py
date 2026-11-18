from __future__ import annotations

from typing import Any

from ecosim.agents.base import AnalysisContext, BaseAgent
from ecosim.agents.citizen_agent import CitizenAgent
from ecosim.agents.economic_agent import EconomicAgent
from ecosim.agents.evidence_agent import EvidenceAgent
from ecosim.agents.policy_agent import PolicyAgent
from ecosim.agents.risk_agent import RiskAgent


class Orchestrator:
    """Coordinates the execution of multiple specialized agents.

    The Orchestrator defines the execution DAG (Directed Acyclic Graph)
    of agents. It ensures that agents run in the correct order so that
    dependencies are met (e.g., EconomicAgent runs before CitizenAgent).

    It compiles all individual agent outputs into a single, cohesive
    multi-agent assessment payload.
    """

    def __init__(self) -> None:
        # Define the specialized agents
        self.economic_agent = EconomicAgent()
        self.citizen_agent = CitizenAgent()
        self.policy_agent = PolicyAgent()
        self.evidence_agent = EvidenceAgent()
        self.risk_agent = RiskAgent()

        self.agents: list[BaseAgent] = [
            self.economic_agent,
            self.citizen_agent,
            self.policy_agent,
            self.evidence_agent,
            self.risk_agent,
        ]

    def run_assessment(self, context: AnalysisContext) -> dict[str, Any]:
        """Execute the full multi-agent assessment workflow.

        Args:
            context: The shared AnalysisContext with request parameters
                     and runtime service references.

        Returns:
            A unified dict containing outputs from all agents.
        """
        result_payload: dict[str, Any] = {}
        executed: list[dict[str, str]] = []
        failed: list[dict[str, str]] = []
        skipped: list[dict[str, str]] = []

        def run_agent(agent: BaseAgent, result_key: str) -> dict[str, Any]:
            """Run one agent without losing results from independent agents."""
            metadata = agent.agent_metadata()
            executed.append(metadata)
            try:
                result = agent.analyze(context)
            except Exception as exc:
                error = {
                    "agent_id": agent.agent_id,
                    "error": f"{agent.agent_name} failed: {exc}",
                }
                failed.append({"agent_id": agent.agent_id, "error": error["error"]})
                result_payload[result_key] = error
                return error

            result_payload[result_key] = result
            if "error" in result:
                failed.append({"agent_id": agent.agent_id, "error": str(result["error"])})
            return result

        # The order is intentional: downstream agents consume these results.
        eco_result = run_agent(self.economic_agent, "economic")
        if "error" not in eco_result:
            context.simulation_result = eco_result

        if context.user_profile:
            citizen_result = run_agent(self.citizen_agent, "citizen")
            if "error" not in citizen_result:
                context.persona_weights = citizen_result.get("persona_weights")
            run_agent(self.policy_agent, "policy")
        else:
            skipped.extend([
                self.citizen_agent.agent_metadata(),
                self.policy_agent.agent_metadata(),
            ])

        run_agent(self.risk_agent, "risk")
        run_agent(self.evidence_agent, "evidence")

        result_payload["_metadata"] = {
            "agents_executed": executed,
            "agents_failed": failed,
            "agents_skipped": skipped,
        }

        return result_payload
