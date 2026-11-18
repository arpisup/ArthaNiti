from __future__ import annotations

import unittest
from pathlib import Path

from ecosim.agents import (
    AnalysisContext,
    EconomicAgent,
    CitizenAgent,
    PolicyAgent,
    EvidenceAgent,
    RiskAgent,
    Orchestrator,
)
from ecosim.profiler import UserProfile
from ecosim.schemes import Scheme, SchemeEligibility, SchemeBenefits
from ecosim.tavily_search import TavilySearchProvider


class DummyEngine:
    def simulate(self, inputs, horizon_years):
        return {
            "macro_metrics": [
                {"id": "gdp_growth_pct", "label": "GDP", "delta": 1.2, "value": 6.0},
                {"id": "inflation_pct", "label": "Inflation", "delta": 0.8, "value": 5.0},
            ],
            "metric_deltas": {
                "gdp_growth_pct": 1.2,
                "inflation_pct": 0.8,
            },
            "highlights": ["GDP up", "Inflation up"],
            "headline": "Modest growth",
            "confidence": {"score": 85, "notes": "Good"},
            "entities": [
                {
                    "id": "mig_households",
                    "metrics": [
                        {"id": "real_income_index", "value": 1.5},
                        {"id": "savings_pressure", "value": -0.2},
                    ]
                },
            ],
            "horizon_years": horizon_years or 5,
            "horizon_bucket": "medium",
            "policy_inputs": inputs or {},
            "policy_defaults": {},
            "normalized_inputs": {"welfare_spending_index": 0.5},
            "baseline_year": 2023,
        }


class DummyIndex:
    pass


def dummy_search(index, query, limit=5):
    return [{"id": "doc1", "snippet": f"Found for {query}"}]

import ecosim.agents.evidence_agent
ecosim.agents.evidence_agent.search_knowledge = dummy_search


class TestAgents(unittest.TestCase):
    def setUp(self):
        self.engine = DummyEngine()
        self.index = DummyIndex()
        self.schemes = [
            Scheme(
                scheme_id="test_scheme",
                name="Test",
                ministry="Test",
                category="subsidy",
                policy_type="welfare",
                government_level="central",
                target_group=["general"],
                eligibility=SchemeEligibility(),
                benefits=SchemeBenefits(),
                economic_sector="general",
                related_indicators=[],
                related_levers=[],
                source_url="",
                active=True,
            )
        ]
        self.profile = {
            "age": 30,
            "state": "Kerala",
            "annual_income": 600000,
            "occupation": "salaried",
            "employment_status": "employed",
        }
        self.context = AnalysisContext(
            policy_inputs={"welfare_spending_index": 110},
            horizon_years=3,
            user_profile=self.profile,
            user_query="How will welfare spending affect food prices for me?",
            engine=self.engine,
            knowledge_index=self.index,
            schemes=self.schemes,
            base_dir=Path("."),
        )

    def test_economic_agent(self):
        agent = EconomicAgent()
        result = agent.analyze(self.context)
        self.assertNotIn("error", result)
        self.assertEqual(result["overall_macro_status"], "mixed")
        self.assertEqual(result["horizon"]["requested_years"], 3)

    def test_citizen_agent(self):
        eco_agent = EconomicAgent()
        eco_result = eco_agent.analyze(self.context)
        self.context.simulation_result = eco_result
        
        agent = CitizenAgent()
        result = agent.analyze(self.context)
        self.assertNotIn("error", result)
        self.assertEqual(result["dominant_persona"], "mig_households")
        self.assertIn("blended_impact", result)

    def test_policy_agent(self):
        agent = PolicyAgent()
        result = agent.analyze(self.context)
        self.assertNotIn("error", result)
        self.assertEqual(result["total_schemes_evaluated"], 1)
        self.assertEqual(result["matched_scheme_count"], 1)

    def test_evidence_agent(self):
        eco_agent = EconomicAgent()
        eco_result = eco_agent.analyze(self.context)
        self.context.simulation_result = eco_result

        agent = EvidenceAgent()
        result = agent.analyze(self.context)
        self.assertNotIn("error", result)
        self.assertIn("food prices", result["query"])
        self.assertIn("welfare spending index", result["query"])
        self.assertEqual(len(result["local_citations"]), 1)
        self.assertGreaterEqual(len(result["citations"]), len(result["local_citations"]))

    def test_tavily_search_normalizes_results(self):
        provider = TavilySearchProvider()
        provider.api_key = "test-key"

        class FakeClient:
            def search(self, query, **kwargs):
                return {"results": [{"title": "Current update", "url": "https://example.com", "content": "Live context"}]}

        provider._client = FakeClient()
        result = provider.search("economic update")

        self.assertEqual(result[0]["provider"], "tavily")
        self.assertEqual(result[0]["url"], "https://example.com")
        self.assertEqual(result[0]["snippet"], "Live context")

    def test_tavily_search_is_optional(self):
        provider = TavilySearchProvider()
        provider.api_key = ""
        self.assertEqual(provider.search("economic update"), [])

    def test_risk_agent(self):
        eco_agent = EconomicAgent()
        eco_result = eco_agent.analyze(self.context)
        self.context.simulation_result = eco_result

        agent = RiskAgent()
        result = agent.analyze(self.context)
        self.assertNotIn("error", result)
        self.assertIn("trade_offs", result)
        self.assertIn("Moderate inflationary trend", result["flagged_risks"])

    def test_orchestrator(self):
        orchestrator = Orchestrator()
        result = orchestrator.run_assessment(self.context)
        
        self.assertIn("economic", result)
        self.assertIn("citizen", result)
        self.assertIn("policy", result)
        self.assertIn("evidence", result)
        self.assertIn("risk", result)
        self.assertIn("_metadata", result)
        self.assertEqual(len(result["_metadata"]["agents_executed"]), 5)
        self.assertEqual(result["_metadata"]["agents_failed"], [])
        self.assertEqual(result["_metadata"]["agents_skipped"], [])

    def test_orchestrator_continues_after_agent_failure(self):
        orchestrator = Orchestrator()

        def failing_analysis(context):
            raise RuntimeError("temporary failure")

        orchestrator.policy_agent.analyze = failing_analysis
        result = orchestrator.run_assessment(self.context)

        self.assertIn("economic", result)
        self.assertIn("risk", result)
        self.assertIn("evidence", result)
        self.assertIn("temporary failure", result["policy"]["error"])
        self.assertEqual(len(result["_metadata"]["agents_failed"]), 1)

    def test_orchestrator_reports_skipped_profile_agents(self):
        context = AnalysisContext(engine=self.engine, knowledge_index=self.index)
        result = Orchestrator().run_assessment(context)

        self.assertNotIn("citizen", result)
        self.assertNotIn("policy", result)
        skipped_ids = {agent["agent_id"] for agent in result["_metadata"]["agents_skipped"]}
        self.assertEqual(skipped_ids, {"citizen_agent", "policy_agent"})


if __name__ == "__main__":
    unittest.main()
