from __future__ import annotations

from typing import Any

from ecosim.agents.base import AnalysisContext, BaseAgent
from ecosim.profiler import parse_user_profile
from ecosim.schemes import match_schemes, scheme_match_payload


class PolicyAgent(BaseAgent):
    """Matches government schemes to the user's profile and situation.

    This agent uses the scheme database to evaluate which active government
    schemes the user is eligible for, scoring relevance based on their
    economic profile, sector, and target group alignment.

    Outputs:
        matched_schemes: List of highly relevant eligible schemes
        matched_scheme_count: Total number of eligible schemes found
        total_schemes_evaluated: Size of the active scheme database
    """

    @property
    def agent_id(self) -> str:
        return "policy_agent"

    @property
    def agent_name(self) -> str:
        return "Policy & Scheme Agent"

    @property
    def description(self) -> str:
        return (
            "Matches individuals with relevant government schemes, subsidies, "
            "and interventions based on their eligibility and needs."
        )

    def analyze(self, context: AnalysisContext) -> dict[str, Any]:
        """Find relevant government schemes for the user."""
        if not context.user_profile:
            return {"error": "No user profile provided"}

        if not context.schemes:
            return {
                "matched_schemes": [],
                "matched_scheme_count": 0,
                "total_schemes_evaluated": 0,
                "error": "No scheme database available",
            }

        try:
            profile = parse_user_profile(context.user_profile)
        except ValueError as exc:
            return {"error": f"Invalid user profile: {exc}"}

        matches = match_schemes(profile, context.schemes, eligible_only=True)

        # Top 15 matches for payload
        top_matches = matches[:15]
        schemes_payload = scheme_match_payload(top_matches)

        return {
            "matched_schemes": schemes_payload,
            "matched_scheme_count": len(matches),
            "total_schemes_evaluated": len(context.schemes),
        }
