from __future__ import annotations

import unittest
from pathlib import Path

from ecosim.model import ScenarioEngine


class ModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.snapshot = {
            "baseline_year": 2024,
            "macro_baseline": {
                "gdp_growth_pct": 6.5,
                "inflation_pct": 4.8,
                "unemployment_pct": 4.2,
                "fiscal_stress_index": 48.0,
                "investment_sentiment_index": 57.0,
                "exchange_stability_index": 68.0,
                "trade_momentum_index": 55.0,
                "household_pressure_index": 42.0,
            },
            "data_quality": {"stale_indicators": []},
        }
        self.engine = ScenarioEngine(Path(__file__).resolve().parents[1], self.snapshot)

    def test_default_simulation_matches_defaults(self) -> None:
        simulation = self.engine.simulate()
        self.assertEqual(simulation["policy_inputs"], self.engine.policy_defaults())
        gdp = next(metric for metric in simulation["macro_metrics"] if metric["id"] == "gdp_growth_pct")
        self.assertEqual(gdp["value"], 6.5)

    def test_growth_push_improves_gdp_and_msmes(self) -> None:
        simulation = self.engine.simulate(
            {
                "infrastructure_push_index": 130,
                "credit_support_index": 130,
                "capital_spending_index": 120,
            },
            horizon_years=10,
        )
        gdp = next(metric for metric in simulation["macro_metrics"] if metric["id"] == "gdp_growth_pct")
        msmes = next(entity for entity in simulation["entities"] if entity["id"] == "msmes")

        self.assertGreater(gdp["value"], 6.5)
        self.assertIn(msmes["status"], {"improving", "steady"})

    def test_social_indicators_change_entity_outcomes(self) -> None:
        base_macro = {
            "gdp_growth_pct": 6.5,
            "inflation_pct": 4.8,
            "unemployment_pct": 4.2,
            "fiscal_stress_index": 48.0,
            "investment_sentiment_index": 57.0,
            "exchange_stability_index": 68.0,
            "trade_momentum_index": 55.0,
            "household_pressure_index": 42.0,
            "poverty_rate_pct": 30.0,
            "internet_users_pct": 35.0,
            "primary_school_enrollment_pct": 72.0,
            "gdp_per_capita_usd": 1200.0,
            "labor_force_participation_pct": 48.0,
            "renewable_energy_share_pct": 18.0,
            "rural_population_pct": 72.0,
        }
        better_macro = {**base_macro, "poverty_rate_pct": 12.0, "internet_users_pct": 82.0, "primary_school_enrollment_pct": 96.0, "gdp_per_capita_usd": 2200.0, "labor_force_participation_pct": 63.0, "renewable_energy_share_pct": 35.0}

        base_engine = self.engine.__class__(Path(__file__).resolve().parents[1], {"baseline_year": 2024, "macro_baseline": base_macro, "data_quality": {"stale_indicators": []}})
        better_engine = self.engine.__class__(Path(__file__).resolve().parents[1], {"baseline_year": 2024, "macro_baseline": better_macro, "data_quality": {"stale_indicators": []}})

        base_score = base_engine._entity_metric_value("lig_households", "real_income_index", base_macro, base_engine.policy_defaults(), base_engine.policy_defaults())
        better_score = better_engine._entity_metric_value("lig_households", "real_income_index", better_macro, better_engine.policy_defaults(), better_engine.policy_defaults())
        self.assertGreater(better_score, base_score)

    def test_policy_scenarios_are_comparable(self) -> None:
        baseline = self.engine.simulate()
        growth = self.engine.simulate({"infrastructure_push_index": 130}, horizon_years=5)

        baseline_gdp = next(metric for metric in baseline["macro_metrics"] if metric["id"] == "gdp_growth_pct")
        growth_gdp = next(metric for metric in growth["macro_metrics"] if metric["id"] == "gdp_growth_pct")
        self.assertGreater(growth_gdp["value"], baseline_gdp["value"])
        self.assertEqual(len(baseline["macro_metrics"]), len(growth["macro_metrics"]))


if __name__ == "__main__":
    unittest.main()
