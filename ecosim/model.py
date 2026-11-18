from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ecosim.processing import clamp

MACRO_WEIGHTS: dict[str, dict[str, float]] = {
    "gdp_growth_pct": {
        "income_tax_rate": -0.80,
        "gst_rate": -0.65,
        "policy_rate": -1.15,
        "capital_spending_index": 0.95,
        "welfare_spending_index": 0.35,
        "subsidy_index": 0.20,
        "credit_support_index": 0.80,
        "export_push_index": 0.75,
        "infrastructure_push_index": 1.10,
        "debt_discipline_index": 0.20,
    },
    "inflation_pct": {
        "income_tax_rate": -0.15,
        "gst_rate": 0.95,
        "policy_rate": -1.10,
        "capital_spending_index": 0.45,
        "welfare_spending_index": 0.60,
        "subsidy_index": 0.75,
        "credit_support_index": 0.40,
        "export_push_index": -0.10,
        "infrastructure_push_index": -0.25,
        "debt_discipline_index": -0.45,
    },
    "unemployment_pct": {
        "income_tax_rate": 0.35,
        "gst_rate": 0.40,
        "policy_rate": 0.80,
        "capital_spending_index": -0.90,
        "welfare_spending_index": -0.20,
        "subsidy_index": -0.15,
        "credit_support_index": -0.85,
        "export_push_index": -0.55,
        "infrastructure_push_index": -0.75,
        "debt_discipline_index": 0.15,
    },
    "fiscal_stress_index": {
        "income_tax_rate": -4.8,
        "gst_rate": -4.1,
        "policy_rate": 0.8,
        "capital_spending_index": 7.2,
        "welfare_spending_index": 6.2,
        "subsidy_index": 6.8,
        "credit_support_index": 2.2,
        "export_push_index": -1.6,
        "infrastructure_push_index": 3.3,
        "debt_discipline_index": -8.0,
    },
    "investment_sentiment_index": {
        "income_tax_rate": -5.0,
        "gst_rate": -2.5,
        "policy_rate": -7.5,
        "capital_spending_index": 4.2,
        "welfare_spending_index": 0.6,
        "subsidy_index": -0.6,
        "credit_support_index": 6.4,
        "export_push_index": 5.1,
        "infrastructure_push_index": 7.0,
        "debt_discipline_index": 4.2,
    },
    "exchange_stability_index": {
        "income_tax_rate": 0.4,
        "gst_rate": -2.4,
        "policy_rate": 3.6,
        "capital_spending_index": -1.2,
        "welfare_spending_index": -1.4,
        "subsidy_index": -2.5,
        "credit_support_index": -1.0,
        "export_push_index": 3.2,
        "infrastructure_push_index": 1.2,
        "debt_discipline_index": 5.2,
    },
    "trade_momentum_index": {
        "income_tax_rate": -1.2,
        "gst_rate": -1.0,
        "policy_rate": -0.8,
        "capital_spending_index": 1.6,
        "welfare_spending_index": 0.3,
        "subsidy_index": 0.1,
        "credit_support_index": 1.8,
        "export_push_index": 8.5,
        "infrastructure_push_index": 4.6,
        "debt_discipline_index": 1.8,
    },
    "household_pressure_index": {
        "income_tax_rate": 3.0,
        "gst_rate": 4.5,
        "policy_rate": 2.2,
        "capital_spending_index": -0.8,
        "welfare_spending_index": -4.4,
        "subsidy_index": -5.4,
        "credit_support_index": -1.4,
        "export_push_index": -0.6,
        "infrastructure_push_index": -1.1,
        "debt_discipline_index": 0.7,
    },
}

HORIZON_LEVER_MULTIPLIERS = {
    1: {
        "capital_spending_index": 0.70,
        "welfare_spending_index": 1.10,
        "subsidy_index": 1.15,
        "credit_support_index": 1.05,
        "export_push_index": 0.75,
        "infrastructure_push_index": 0.65,
        "debt_discipline_index": 0.80,
    },
    5: {
        "capital_spending_index": 1.00,
        "welfare_spending_index": 1.00,
        "subsidy_index": 1.00,
        "credit_support_index": 1.00,
        "export_push_index": 1.00,
        "infrastructure_push_index": 1.00,
        "debt_discipline_index": 1.00,
    },
    10: {
        "capital_spending_index": 1.18,
        "welfare_spending_index": 0.80,
        "subsidy_index": 0.75,
        "credit_support_index": 0.92,
        "export_push_index": 1.18,
        "infrastructure_push_index": 1.28,
        "debt_discipline_index": 1.20,
    },
}

MACRO_LIMITS = {
    "gdp_growth_pct": (-2.0, 12.0),
    "inflation_pct": (0.5, 15.0),
    "unemployment_pct": (2.0, 15.0),
    "fiscal_stress_index": (0.0, 100.0),
    "investment_sentiment_index": (0.0, 100.0),
    "exchange_stability_index": (0.0, 100.0),
    "trade_momentum_index": (0.0, 100.0),
    "household_pressure_index": (0.0, 100.0),
}


@dataclass(frozen=True)
class PolicyLever:
    id: str
    label: str
    unit: str
    minimum: float
    maximum: float
    step: float
    baseline: float
    description: str

    @property
    def span(self) -> float:
        return max(abs(self.maximum - self.baseline), abs(self.minimum - self.baseline), 1.0)


def _round_metric(metric_id: str, value: float) -> float:
    if metric_id.endswith("_pct"):
        return round(value, 2)
    return round(value, 1)


def _horizon_bucket(years: int) -> int:
    if years <= 2:
        return 1
    if years <= 7:
        return 5
    return 10


def _safe_relative_change(current: float, baseline: float) -> float:
    if baseline == 0:
        return 0.0
    return ((current - baseline) / abs(baseline)) * 100


class ScenarioEngine:
    def __init__(self, base_dir: Path, snapshot: dict[str, Any]) -> None:
        self.base_dir = base_dir
        self.snapshot = snapshot
        self.config = self._load_model_config(base_dir / "configs/policy_model.json")
        self.policy_levers = self._load_policy_levers()
        self.entities = self._load_entities(base_dir / "configs/colony_entities.json")

    def _load_model_config(self, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def _load_policy_levers(self) -> list[PolicyLever]:
        levers: list[PolicyLever] = []
        for item in self.config["policy_levers"]:
            levers.append(
                PolicyLever(
                    id=item["id"],
                    label=item["label"],
                    unit=item["unit"],
                    minimum=float(item["min"]),
                    maximum=float(item["max"]),
                    step=float(item["step"]),
                    baseline=float(item["baseline"]),
                    description=item["description"],
                )
            )
        return levers

    def _load_entities(self, path: Path) -> list[dict[str, Any]]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload["entities"]

    def policy_defaults(self) -> dict[str, float]:
        return {lever.id: lever.baseline for lever in self.policy_levers}

    def supported_horizons(self) -> list[int]:
        return list(self.config["supported_horizons"])

    def normalize_inputs(self, inputs: Mapping[str, Any] | None) -> tuple[dict[str, float], dict[str, float]]:
        raw_inputs = dict(inputs or {})
        values: dict[str, float] = {}
        normalized: dict[str, float] = {}
        for lever in self.policy_levers:
            try:
                raw_value = float(raw_inputs.get(lever.id, lever.baseline))
            except (TypeError, ValueError):
                raw_value = lever.baseline
            clamped = clamp(raw_value, lever.minimum, lever.maximum)
            values[lever.id] = clamped
            normalized[lever.id] = (clamped - lever.baseline) / lever.span
        return values, normalized

    def _apply_feedback(self, metrics: dict[str, float], deltas: dict[str, float]) -> None:
        metrics["investment_sentiment_index"] += (
            deltas["gdp_growth_pct"] * 3.2
            - deltas["inflation_pct"] * 2.1
            - deltas["fiscal_stress_index"] * 0.25
        )
        metrics["household_pressure_index"] += (
            deltas["inflation_pct"] * 4.0
            + deltas["unemployment_pct"] * 3.4
            - deltas["gdp_growth_pct"] * 2.2
        )
        metrics["exchange_stability_index"] += (
            deltas["trade_momentum_index"] * 0.22
            - deltas["inflation_pct"] * 1.8
            - deltas["fiscal_stress_index"] * 0.18
        )
        metrics["trade_momentum_index"] += deltas["gdp_growth_pct"] * 1.1

    def _build_macro_metrics(
        self,
        normalized_inputs: dict[str, float],
        horizon_years: int,
    ) -> tuple[dict[str, float], dict[str, float]]:
        bucket = _horizon_bucket(horizon_years)
        horizon_weights = HORIZON_LEVER_MULTIPLIERS[bucket]
        baseline = self.snapshot["macro_baseline"]
        deltas: dict[str, float] = {}
        simulated: dict[str, float] = {}

        for metric_id, weights in MACRO_WEIGHTS.items():
            raw_delta = 0.0
            for lever_id, weight in weights.items():
                horizon_multiplier = horizon_weights.get(lever_id, 1.0)
                raw_delta += normalized_inputs.get(lever_id, 0.0) * weight * horizon_multiplier
            deltas[metric_id] = raw_delta
            minimum, maximum = MACRO_LIMITS[metric_id]
            simulated[metric_id] = clamp(baseline[metric_id] + raw_delta, minimum, maximum)

        self._apply_feedback(simulated, deltas)
        for metric_id, (minimum, maximum) in MACRO_LIMITS.items():
            simulated[metric_id] = _round_metric(metric_id, clamp(simulated[metric_id], minimum, maximum))
            deltas[metric_id] = _round_metric(metric_id, simulated[metric_id] - baseline[metric_id])

        return simulated, deltas

    def _entity_metric_value(
        self,
        entity_id: str,
        metric_id: str,
        macro: dict[str, float],
        policy_inputs: dict[str, float],
        policy_defaults: dict[str, float],
    ) -> float:
        gdp = macro["gdp_growth_pct"]
        inflation = macro["inflation_pct"]
        unemployment = macro["unemployment_pct"]
        fiscal = macro["fiscal_stress_index"]
        investment = macro["investment_sentiment_index"]
        household = macro["household_pressure_index"]
        trade = macro["trade_momentum_index"]
        exchange = macro["exchange_stability_index"]
        poverty = macro.get("poverty_rate_pct", 15.0)
        internet = macro.get("internet_users_pct", 50.0)
        schooling = macro.get("primary_school_enrollment_pct", 80.0)
        gdp_per_capita = macro.get("gdp_per_capita_usd", 1500.0) / 1000.0
        labor_force = macro.get("labor_force_participation_pct", 55.0)
        renewable_share = macro.get("renewable_energy_share_pct", 20.0)
        rural_share = macro.get("rural_population_pct", 50.0)
        policy_rate = policy_inputs["policy_rate"]
        gst = policy_inputs["gst_rate"]
        income_tax = policy_inputs["income_tax_rate"]
        welfare_delta = policy_inputs["welfare_spending_index"] - policy_defaults["welfare_spending_index"]
        subsidy_delta = policy_inputs["subsidy_index"] - policy_defaults["subsidy_index"]
        credit_delta = policy_inputs["credit_support_index"] - policy_defaults["credit_support_index"]
        infra_delta = policy_inputs["infrastructure_push_index"] - policy_defaults["infrastructure_push_index"]
        capex_delta = policy_inputs["capital_spending_index"] - policy_defaults["capital_spending_index"]

        formulas = {
            ("lig_households", "real_income_index"): 58 + gdp * 1.9 - inflation * 2.6 - unemployment * 2.1 + welfare_delta * 0.12 + subsidy_delta * 0.10 + gdp_per_capita * 1.4 + internet * 0.15 + labor_force * 0.12 - poverty * 0.18,
            ("lig_households", "inflation_pressure"): 28 + inflation * 4.2 + (gst - policy_defaults["gst_rate"]) * 1.8 - subsidy_delta * 0.05,
            ("lig_households", "employment_stability"): 70 + gdp * 2.4 - unemployment * 5.2 + credit_delta * 0.08 + labor_force * 0.18 - poverty * 0.12,
            ("mig_households", "real_income_index"): 60 + gdp * 1.8 - inflation * 2.2 - unemployment * 1.8 + gdp_per_capita * 1.1 + internet * 0.09,
            ("mig_households", "savings_pressure"): 30 + inflation * 3.5 + policy_rate * 2.6 + (income_tax - policy_defaults["income_tax_rate"]) * 0.9 - internet * 0.05,
            ("mig_households", "housing_cost_index"): 38 + inflation * 2.0 + policy_rate * 3.1 + (gst - policy_defaults["gst_rate"]) * 1.2 + poverty * 0.08,
            ("hig_households", "investment_sentiment"): 22 + investment * 0.75 - (income_tax - policy_defaults["income_tax_rate"]) * 1.3 + internet * 0.12 + schooling * 0.10,
            ("hig_households", "tax_burden_index"): 25 + income_tax * 2.2 + gst * 0.8 - schooling * 0.05,
            ("hig_households", "consumption_outlook"): 28 + gdp * 3.0 + investment * 0.4 - inflation * 1.5 + gdp_per_capita * 1.5 + internet * 0.08,
            ("farmers", "input_cost_index"): 30 + inflation * 3.0 + exchange * -0.18 - subsidy_delta * 0.08 + rural_share * 0.10,
            ("farmers", "crop_income_outlook"): 32 + gdp * 2.1 + trade * 0.35 + subsidy_delta * 0.05 + renewable_share * 0.22 + gdp_per_capita * 0.8,
            ("farmers", "credit_access"): 35 + credit_delta * 0.30 + investment * 0.35 - policy_rate * 2.2 + schooling * 0.05,
            ("msmes", "operating_cost_index"): 32 + inflation * 3.2 + policy_rate * 1.8 + (gst - policy_defaults["gst_rate"]) * 1.1 - internet * 0.04,
            ("msmes", "credit_access"): 30 + credit_delta * 0.35 + investment * 0.45 - policy_rate * 2.6 + schooling * 0.08,
            ("msmes", "demand_outlook"): 28 + gdp * 3.0 + household * -0.35 + trade * 0.22 + internet * 0.16 + labor_force * 0.18,
            ("public_services", "service_capacity"): 26 + capex_delta * 0.18 + welfare_delta * 0.12 - fiscal * 0.18 + schooling * 0.20 + internet * 0.10,
            ("public_services", "public_spend_signal"): 32 + capex_delta * 0.22 + welfare_delta * 0.18 + subsidy_delta * 0.10 + gdp_per_capita * 0.9,
            ("public_services", "infrastructure_score"): 20 + infra_delta * 0.32 + capex_delta * 0.15 + exchange * 0.15 + renewable_share * 0.18 + internet * 0.08,
            ("market_activity", "consumer_demand"): 26 + gdp * 2.8 - household * 0.30 + welfare_delta * 0.08 + internet * 0.12 + gdp_per_capita * 1.2,
            ("market_activity", "price_momentum"): 24 + inflation * 4.0 + trade * 0.15 + poverty * 0.12,
            ("market_activity", "inventory_flow"): 25 + trade * 0.45 + exchange * 0.15 + gdp * 1.2 + internet * 0.08,
        }

        value = formulas[(entity_id, metric_id)]
        return round(clamp(value, 0, 100), 1)

    def _entity_status(self, delta: float) -> str:
        if delta >= 5:
            return "improving"
        if delta <= -5:
            return "stressed"
        return "steady"

    def _entity_headline(self, metrics: list[dict[str, Any]]) -> str:
        strongest = max(metrics, key=lambda item: abs(item["delta"]))
        direction = "up" if strongest["delta"] >= 0 else "down"
        return f"{strongest['label']} is the biggest mover, {direction} {abs(strongest['delta']):.1f}."

    def _build_entities(
        self,
        simulated_macro: dict[str, float],
        baseline_macro: dict[str, float],
        policy_inputs: dict[str, float],
        policy_defaults: dict[str, float],
    ) -> list[dict[str, Any]]:
        baseline_entity_metrics: dict[str, list[dict[str, Any]]] = {}
        simulated_entity_metrics: dict[str, list[dict[str, Any]]] = {}

        for entity in self.entities:
            base_metrics: list[dict[str, Any]] = []
            sim_metrics: list[dict[str, Any]] = []
            for metric_id in entity["primary_metrics"]:
                label = metric_id.replace("_", " ").replace("pct", "").title()
                base_value = self._entity_metric_value(
                    entity["id"], metric_id, baseline_macro, policy_defaults, policy_defaults
                )
                sim_value = self._entity_metric_value(
                    entity["id"], metric_id, simulated_macro, policy_inputs, policy_defaults
                )
                base_metrics.append({"id": metric_id, "label": label, "value": base_value})
                sim_metrics.append(
                    {
                        "id": metric_id,
                        "label": label,
                        "baseline": base_value,
                        "value": sim_value,
                        "delta": round(sim_value - base_value, 1),
                    }
                )
            baseline_entity_metrics[entity["id"]] = base_metrics
            simulated_entity_metrics[entity["id"]] = sim_metrics

        entities_payload: list[dict[str, Any]] = []
        for entity in self.entities:
            metrics = simulated_entity_metrics[entity["id"]]
            average_delta = round(sum(metric["delta"] for metric in metrics) / len(metrics), 1)
            entities_payload.append(
                {
                    "id": entity["id"],
                    "label": entity["label"],
                    "archetype": entity["archetype"],
                    "notes": entity.get("notes", ""),
                    "scene": entity.get("scene", {}),
                    "status": self._entity_status(average_delta),
                    "delta": average_delta,
                    "headline": self._entity_headline(metrics),
                    "metrics": metrics,
                }
            )
        return entities_payload

    def _confidence(self, normalized_inputs: dict[str, float]) -> dict[str, Any]:
        quality = self.snapshot["data_quality"]
        intensity = sum(abs(value) for value in normalized_inputs.values()) / max(len(normalized_inputs), 1)
        stale_penalty = min(len(quality["stale_indicators"]) * 3.0, 18.0)
        score = clamp(86 - intensity * 24 - stale_penalty, 35, 92)
        return {
            "score": round(score, 1),
            "scenario_intensity": round(intensity * 100, 1),
            "stale_indicators": quality["stale_indicators"],
            "notes": [
                "This is a transparent scenario engine, not a causal econometric model.",
                "The baseline is grounded in the latest processed World Bank snapshot available in the repo.",
            ],
        }

    def _scenario_headline(self, normalized_inputs: dict[str, float], entities: list[dict[str, Any]]) -> str:
        sorted_levers = sorted(normalized_inputs.items(), key=lambda item: abs(item[1]), reverse=True)
        top_levers = [lever_id for lever_id, value in sorted_levers if abs(value) > 0.05][:2]
        if not top_levers:
            return "Baseline policy stance with no major deviations."

        improving = [entity["label"] for entity in entities if entity["status"] == "improving"]
        stressed = [entity["label"] for entity in entities if entity["status"] == "stressed"]
        positive = ", ".join(improving[:2]) if improving else "few personas"
        negative = ", ".join(stressed[:2]) if stressed else "limited downside"
        lever_labels = [next(lever.label for lever in self.policy_levers if lever.id == lever_id) for lever_id in top_levers]
        return f"Scenario is mainly driven by {', '.join(lever_labels)}; upside is strongest for {positive}, while pressure remains on {negative}."

    def simulate(self, inputs: Mapping[str, Any] | None = None, horizon_years: int | None = None) -> dict[str, Any]:
        requested_horizon = int(horizon_years or self.config["default_horizon_years"])
        bucket = _horizon_bucket(requested_horizon)
        policy_inputs, normalized_inputs = self.normalize_inputs(inputs)
        baseline_macro = {
            metric["id"]: self.snapshot["macro_baseline"][metric["id"]]
            for metric in self.config["macro_metrics"]
        }
        simulated_macro, metric_deltas = self._build_macro_metrics(normalized_inputs, requested_horizon)
        policy_defaults = self.policy_defaults()
        entities = self._build_entities(simulated_macro, baseline_macro, policy_inputs, policy_defaults)

        macro_payload = []
        for metric in self.config["macro_metrics"]:
            metric_id = metric["id"]
            baseline_value = _round_metric(metric_id, baseline_macro[metric_id])
            value = simulated_macro[metric_id]
            delta = _round_metric(metric_id, value - baseline_value)
            macro_payload.append(
                {
                    "id": metric_id,
                    "label": metric["label"],
                    "unit": metric["unit"],
                    "precision": metric["precision"],
                    "baseline": baseline_value,
                    "value": value,
                    "delta": delta,
                    "relative_change_pct": round(_safe_relative_change(value, baseline_value), 1),
                }
            )

        strongest_metrics = sorted(macro_payload, key=lambda item: abs(item["delta"]), reverse=True)[:3]
        return {
            "baseline_year": self.snapshot["baseline_year"],
            "horizon_years": requested_horizon,
            "horizon_bucket": bucket,
            "policy_inputs": policy_inputs,
            "policy_defaults": policy_defaults,
            "normalized_inputs": normalized_inputs,
            "macro_metrics": macro_payload,
            "metric_deltas": metric_deltas,
            "entities": entities,
            "confidence": self._confidence(normalized_inputs),
            "headline": self._scenario_headline(normalized_inputs, entities),
            "highlights": [
                f"{item['label']} moves {item['delta']:+} {item['unit']}".strip()
                for item in strongest_metrics
            ],
        }
