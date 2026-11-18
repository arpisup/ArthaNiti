from __future__ import annotations

from typing import Any

from ecosim.agents.base import AnalysisContext, BaseAgent
from ecosim.profiler import (
    compute_macro_exposure,
    parse_user_profile,
    personalized_impact,
    profile_summary,
    profile_to_persona_weights,
)


class CitizenAgent(BaseAgent):
    """Assesses individual-level impact based on user profile.

    This agent depends on the output of the EconomicAgent (the
    `simulation_result`). It takes the user profile, maps it to
    persona weights, and blends the persona-level impacts to determine
    the personalized impact on the user.

    Outputs:
        profile: structured summary of the user's demographic/economic profile
        persona_weights: mapping of persona ID to relevance weight (sums to 1)
        blended_impact: weighted sum of simulated metrics
        macro_exposure: 0-100 scores indicating the user's sensitivity to macro changes
        dominant_persona: the persona that best fits the user
        overall_status: positive/negative/mixed assessment for this specific user
        headline: one-sentence impact summary personalized to the user
    """

    @property
    def agent_id(self) -> str:
        return "citizen_agent"

    @property
    def agent_name(self) -> str:
        return "Citizen Impact Agent"

    @property
    def description(self) -> str:
        return (
            "Translates national macroeconomic changes into personalized "
            "individual-level impacts based on a user's demographic and "
            "economic profile."
        )

    def analyze(self, context: AnalysisContext) -> dict[str, Any]:
        """Assess personalized impact using user profile and simulation results."""
        if not context.user_profile:
            return {"error": "No user profile provided"}

        if not context.simulation_result:
            return {"error": "Simulation result required (EconomicAgent must run first)"}

        try:
            profile = parse_user_profile(context.user_profile)
        except ValueError as exc:
            return {"error": f"Invalid user profile: {exc}"}

        # 1. Profile to persona mapping
        persona_weights = profile_to_persona_weights(profile)

        # 2. Blend simulation metrics
        impact = personalized_impact(context.simulation_result, persona_weights)

        # 3. Compute structural macro exposure
        exposure = compute_macro_exposure(profile)

        # 4. Profile summary
        summary = profile_summary(profile)

        return {
            "profile": summary,
            "persona_weights": persona_weights,
            "blended_impact": impact["blended_metrics"],
            "macro_exposure": exposure,
            "dominant_persona": impact["dominant_persona"],
            "overall_status": impact["overall_status"],
            "headline": impact["headline"],
        }
