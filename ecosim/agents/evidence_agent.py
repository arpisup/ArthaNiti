from __future__ import annotations

from typing import Any

from ecosim.agents.base import AnalysisContext, BaseAgent
from ecosim.knowledge import search_knowledge
from ecosim.tavily_search import TavilySearchProvider


class EvidenceAgent(BaseAgent):
    """Retrieves relevant knowledge base context and citations.

    This agent examines the user profile and the scenario's dominant policy
    levers and macro shifts (from the EconomicAgent output) to form targeted
    search queries against the local knowledge index.

    Outputs:
        query: The synthesized search query
        citations: List of matched documents/chunks with source info and snippets
    """

    @property
    def agent_id(self) -> str:
        return "evidence_agent"

    @property
    def agent_name(self) -> str:
        return "Evidence & Knowledge Agent"

    @property
    def description(self) -> str:
        return (
            "Retrieves supporting evidence, domain context, and citations "
            "from the local project knowledge base to ground the assessment."
        )

    def analyze(self, context: AnalysisContext) -> dict[str, Any]:
        """Retrieve contextual evidence from the knowledge base."""
        query_terms: list[str] = []

        # Preserve the user's intent so retrieval answers the question they asked.
        if context.user_query:
            query_terms.append(context.user_query)

        # Add context from user profile
        if context.user_profile:
            # We don't strictly need to parse into a UserProfile here, dict access is fine
            occ = context.user_profile.get("occupation", "")
            sector = context.user_profile.get("sector", "")
            if occ:
                query_terms.append(str(occ))
            if sector:
                query_terms.append(str(sector))

        # Add context from dominant macro shifts (if EconomicAgent ran)
        if context.simulation_result:
            sim = context.simulation_result
            
            # Top policy levers changed
            strongest_levers = sorted(
                sim.get("normalized_inputs", {}).items(),
                key=lambda item: abs(item[1]),
                reverse=True,
            )[:2]
            for lever_id, _ in strongest_levers:
                query_terms.append(lever_id.replace("_", " "))

            # Top macro metrics shifted
            strongest_metrics = sorted(
                sim.get("macro_metrics", []),
                key=lambda item: abs(item.get("delta", 0)),
                reverse=True,
            )[:2]
            for metric in strongest_metrics:
                query_terms.append(metric.get("label", ""))

        if not query_terms:
            query = "economic policy impact"
        else:
            query = " ".join(query_terms)

        citations = search_knowledge(context.knowledge_index, query, limit=3) if context.knowledge_index else []
        live_citations = TavilySearchProvider().search(query, limit=3)

        return {
            "query": query,
            "citations": citations + live_citations,
            "local_citations": citations,
            "live_citations": live_citations,
            "live_search_enabled": bool(live_citations),
        }
