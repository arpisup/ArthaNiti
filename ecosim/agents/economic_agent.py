from __future__ import annotations

from typing import Any

from ecosim.agents.base import AnalysisContext, BaseAgent


class EconomicAgent(BaseAgent):
    """Assesses national-level macroeconomic impact of policy changes.

    This agent wraps the ScenarioEngine to evaluate how policy lever
    adjustments affect GDP growth, inflation, unemployment, fiscal stress,
    investment sentiment, exchange stability, trade momentum, and
    household pressure.

    It operates at the country level — it does not consider individual
    user characteristics. That responsibility belongs to the CitizenAgent.

    Outputs:
        macro_metrics: list of metric dicts with baseline, simulated, and delta values
        metric_deltas: dict mapping metric_id to delta value
        highlights: top 3 most-affected metrics as human-readable strings
        headline: one-sentence scenario summary
        confidence: model confidence score and notes
        entities: per-persona impact breakdown (for downstream agents)
        horizon: simulation time horizon details
    """

    @property
    def agent_id(self) -> str:
        return "economic_agent"

    @property
    def agent_name(self) -> str:
        return "Economic Impact Agent"

    @property
    def description(self) -> str:
        return (
            "Evaluates the national-level macroeconomic impact of policy "
            "changes on GDP, inflation, unemployment, fiscal position, "
            "investment climate, and trade."
        )

    def analyze(self, context: AnalysisContext) -> dict[str, Any]:
        """Run the scenario simulation and return macro-level results."""
        engine = context.engine
        if engine is None:
            return {"error": "ScenarioEngine not available in context"}

        simulation = engine.simulate(
            inputs=context.policy_inputs,
            horizon_years=context.horizon_years,
        )

        # Classify macro-level status
        macro_metrics = simulation["macro_metrics"]
        improving_count = sum(1 for m in macro_metrics if m["delta"] > 0.5)
        worsening_count = sum(1 for m in macro_metrics if m["delta"] < -0.5)

        if improving_count > worsening_count + 2:
            overall_macro_status = "positive"
        elif worsening_count > improving_count + 2:
            overall_macro_status = "negative"
        else:
            overall_macro_status = "mixed"

        return {
            "macro_metrics": simulation["macro_metrics"],
            "metric_deltas": simulation["metric_deltas"],
            "highlights": simulation["highlights"],
            "headline": simulation["headline"],
            "confidence": simulation["confidence"],
            "entities": simulation["entities"],
            "overall_macro_status": overall_macro_status,
            "horizon": {
                "requested_years": simulation["horizon_years"],
                "bucket": simulation["horizon_bucket"],
            },
            "policy_inputs": simulation["policy_inputs"],
            "policy_defaults": simulation["policy_defaults"],
            "normalized_inputs": simulation["normalized_inputs"],
            "baseline_year": simulation["baseline_year"],
        }
