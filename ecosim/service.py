from __future__ import annotations

from pathlib import Path
from typing import Any

from ecosim.agents import AnalysisContext, Orchestrator
from ecosim.auth import AuthManager
from ecosim.llm import parse_policy_intent, generate_chat_response
from ecosim.knowledge import build_knowledge_index, load_knowledge_index, search_knowledge
from ecosim.model import ScenarioEngine
from ecosim.processing import load_processed_snapshot, prepare_processed_data
from ecosim.profiler import (
    UserProfile,
    compute_macro_exposure,
    parse_user_profile,
    personalized_impact,
    profile_summary,
    profile_to_persona_weights,
)
from ecosim.schemes import load_schemes, match_schemes, scheme_match_payload
from ecosim.tavily_search import TavilySearchProvider


class EcoSimService:
    def __init__(self, base_dir: Path, auto_build: bool = True) -> None:
        self.base_dir = base_dir.resolve()
        if auto_build:
            self.ensure_runtime_artifacts()
        self.snapshot = load_processed_snapshot(self.base_dir)
        self.knowledge_index = load_knowledge_index(self.base_dir)
        self.engine = ScenarioEngine(self.base_dir, self.snapshot)
        self.schemes = load_schemes(self.base_dir)
        self.orchestrator = Orchestrator()
        self.auth = AuthManager(self.base_dir / "data/users.db")

    def ensure_runtime_artifacts(self) -> None:
        processed_path = self.base_dir / "data/processed/latest/snapshot.json"
        if not processed_path.exists():
            prepare_processed_data(self.base_dir)

        knowledge_path = self.base_dir / "data/knowledge/latest/index.json"
        if not knowledge_path.exists():
            build_knowledge_index(self.base_dir)

    def config_payload(self) -> dict[str, Any]:
        return {
            "project": {
                "name": "Eco Sim",
                "baseline_year": self.snapshot["baseline_year"],
            },
            "supported_horizons": self.engine.supported_horizons(),
            "default_horizon_years": self.engine.config["default_horizon_years"],
            "policy_levers": [
                {
                    "id": lever.id,
                    "label": lever.label,
                    "unit": lever.unit,
                    "min": lever.minimum,
                    "max": lever.maximum,
                    "step": lever.step,
                    "baseline": lever.baseline,
                    "description": lever.description,
                }
                for lever in self.engine.policy_levers
            ],
            "macro_metrics": self.engine.config["macro_metrics"],
            "entities": self.engine.entities,
            "live_search": {"provider": "tavily", "enabled": TavilySearchProvider().enabled},
        }

    def baseline_payload(self) -> dict[str, Any]:
        default_simulation = self.engine.simulate()
        assessment = self.multi_agent_assess_payload({
            "horizon_years": default_simulation["horizon_years"],
            "policy_inputs": default_simulation["policy_inputs"],
            "user_query": "Baseline policy stance",
        })
        return {
            "snapshot": self.snapshot,
            "default_policy_inputs": self.engine.policy_defaults(),
            "default_simulation": default_simulation,
            "assessment": assessment,
        }

    def simulate_payload(self, payload: dict[str, Any] | None) -> dict[str, Any]:
        payload = payload or {}
        return self.engine.simulate(
            inputs=payload.get("policy_inputs"),
            horizon_years=payload.get("horizon_years"),
        )

    def compare_payload(self, payload: dict[str, Any] | None) -> dict[str, Any]:
        """Compare two policy scenarios using the deterministic scenario engine."""
        payload = payload or {}
        scenario_a = payload.get("scenario_a") or {}
        scenario_b = payload.get("scenario_b") or {}
        simulation_a = self.engine.simulate(
            inputs=scenario_a.get("policy_inputs"),
            horizon_years=scenario_a.get("horizon_years"),
        )
        simulation_b = self.engine.simulate(
            inputs=scenario_b.get("policy_inputs"),
            horizon_years=scenario_b.get("horizon_years"),
        )

        metrics_b = {metric["id"]: metric for metric in simulation_b["macro_metrics"]}
        metrics = []
        for metric in simulation_a["macro_metrics"]:
            other = metrics_b[metric["id"]]
            metrics.append({
                "id": metric["id"],
                "label": metric["label"],
                "unit": metric["unit"],
                "scenario_a": metric["value"],
                "scenario_b": other["value"],
                "difference_b_minus_a": round(other["value"] - metric["value"], 2),
            })

        gdp = next(metric for metric in metrics if metric["id"] == "gdp_growth_pct")
        inflation = next(metric for metric in metrics if metric["id"] == "inflation_pct")
        label_a = scenario_a.get("label", "Scenario A")
        label_b = scenario_b.get("label", "Scenario B")
        return {
            "scenario_a": {"label": label_a, "simulation": simulation_a},
            "scenario_b": {"label": label_b, "simulation": simulation_b},
            "metrics": metrics,
            "summary": {
                "higher_gdp_scenario": label_a if gdp["scenario_a"] >= gdp["scenario_b"] else label_b,
                "gdp_difference_b_minus_a": gdp["difference_b_minus_a"],
                "lower_inflation_scenario": label_a if inflation["scenario_a"] <= inflation["scenario_b"] else label_b,
            },
        }

    def explain_payload(self, payload: dict[str, Any] | None) -> dict[str, Any]:
        payload = payload or {}
        selected_entity_id = payload.get("selected_entity_id")
        simulation = self.simulate_payload(payload)
        entities = {entity["id"]: entity for entity in simulation["entities"]}
        selected_entity = entities.get(selected_entity_id) or simulation["entities"][0]
        strongest_levers = sorted(
            simulation["normalized_inputs"].items(),
            key=lambda item: abs(item[1]),
            reverse=True,
        )[:3]
        strongest_metrics = sorted(
            simulation["macro_metrics"],
            key=lambda item: abs(item["delta"]),
            reverse=True,
        )[:3]

        query_terms = [
            selected_entity["label"],
            *[lever_id.replace("_", " ") for lever_id, _ in strongest_levers],
            *[metric["label"] for metric in strongest_metrics],
        ]
        query = " ".join(query_terms)
        citations = search_knowledge(self.knowledge_index, query, limit=3)

        def _format_metric_delta(metric: dict[str, Any]) -> str:
            if metric["unit"] == "%":
                return f"{metric['label']} {metric['delta']:+}%"
            return f"{metric['label']} {metric['delta']:+} pts"

        macro_sentence = ", ".join(_format_metric_delta(metric) for metric in strongest_metrics)
        entity_sentence = ", ".join(
            f"{metric['label']} {metric['delta']:+.1f}"
            for metric in selected_entity["metrics"]
        )
        lever_sentence = ", ".join(
            f"{lever_id.replace('_', ' ')} {value:+.2f}"
            for lever_id, value in strongest_levers
            if abs(value) > 0.01
        )
        if not lever_sentence:
            lever_sentence = "no major lever deviations"

        narrative = (
            f"Over the {simulation['horizon_years']}-year horizon, the biggest modeled macro moves are {macro_sentence}. "
            f"For {selected_entity['label']}, the model reads the situation as {selected_entity['status']}: {entity_sentence}. "
            f"The scenario is mainly being driven by {lever_sentence}. "
            "Supporting context below comes from the local project knowledge base, not from a generative model."
        )

        return {
            "narrative": narrative,
            "selected_entity": selected_entity,
            "simulation": simulation,
            "query": query,
            "citations": citations,
        }

    def knowledge_search_payload(self, query: str, limit: int = 5) -> dict[str, Any]:
        return {
            "query": query,
            "results": search_knowledge(self.knowledge_index, query, limit=limit),
        }

    def profile_impact_payload(self, payload: dict[str, Any] | None) -> dict[str, Any]:
        """Compute personalized policy impact for a user profile.

        Accepts a payload containing 'user_profile' and optionally
        'policy_inputs' and 'horizon_years'. Returns blended persona
        impact, macro exposure scores, profile summary, and matched schemes.
        """
        payload = payload or {}
        profile_data = payload.get("user_profile", {})
        profile = parse_user_profile(profile_data)

        # Compute persona weights from user profile
        persona_weights = profile_to_persona_weights(profile)

        # Run the simulation
        simulation = self.engine.simulate(
            inputs=payload.get("policy_inputs"),
            horizon_years=payload.get("horizon_years"),
        )

        # Compute personalized blended impact
        blended = personalized_impact(simulation, persona_weights)

        # Compute macro exposure scores
        exposure = compute_macro_exposure(profile)

        # Match schemes
        matches = match_schemes(profile, self.schemes, eligible_only=True)
        schemes_payload = scheme_match_payload(matches[:15])  # Top 15 matches

        return {
            "profile": profile_summary(profile),
            "persona_weights": persona_weights,
            "blended_impact": blended,
            "macro_exposure": exposure,
            "simulation": simulation,
            "matched_schemes": schemes_payload,
            "matched_scheme_count": len(matches),
        }

    def scheme_match_only_payload(self, payload: dict[str, Any] | None) -> dict[str, Any]:
        """Match schemes for a user profile without running a simulation.

        Accepts a payload containing 'user_profile'. Returns all eligible
        schemes sorted by relevance.
        """
        payload = payload or {}
        profile_data = payload.get("user_profile", {})
        profile = parse_user_profile(profile_data)

        matches = match_schemes(profile, self.schemes, eligible_only=True)
    def multi_agent_assess_payload(self, payload: dict[str, Any] | None) -> dict[str, Any]:
        """Perform a full multi-agent assessment.

        This delegates entirely to the Orchestrator, which runs the
        Economic, Citizen, Policy, Risk, and Evidence agents in the
        correct sequence.
        """
        payload = payload or {}
        
        context = AnalysisContext(
            policy_inputs=payload.get("policy_inputs"),
            horizon_years=payload.get("horizon_years"),
            user_profile=payload.get("user_profile"),
            user_query=payload.get("user_query"),
            engine=self.engine,
            knowledge_index=self.knowledge_index,
            schemes=self.schemes,
            snapshot=self.snapshot,
            base_dir=self.base_dir,
        )
        return self.orchestrator.run_assessment(context)

    def chat_payload(self, payload: dict[str, Any] | None, token: str | None = None) -> dict[str, Any]:
        """Process a natural language chat query."""
        payload = payload or {}
        message = payload.get("message", "")
        
        if not message:
            return {"error": "Message is required"}

        # 1. Authenticate user profile (if any)
        user_profile = None
        if token:
            user = self.auth.get_user_by_token(token)
            if user:
                user_profile = user["profile"]

        # 2. Extract policy intent via LLM
        intent = parse_policy_intent(message)
        
        # 3. Run Multi-Agent Assessment
        context = AnalysisContext(
            policy_inputs=intent.get("policy_inputs"),
            horizon_years=intent.get("horizon_years"),
            user_query=message,
            user_profile=user_profile,
            engine=self.engine,
            knowledge_index=self.knowledge_index,
            schemes=self.schemes,
            snapshot=self.snapshot,
            base_dir=self.base_dir,
        )
        mas_result = self.orchestrator.run_assessment(context)
        
        # 4. Generate Conversational Response via LLM
        reply = generate_chat_response(message, mas_result)
        
        return {
            "reply": reply,
            "mas_data": mas_result,
            "intent": intent
        }
