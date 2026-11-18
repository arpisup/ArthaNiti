from __future__ import annotations

import unittest
from unittest.mock import patch

from ecosim import llm


class LlmTests(unittest.TestCase):
    def test_parser_keeps_only_configured_policy_ids(self) -> None:
        response = '{"policy_inputs": {"gst_rate": 20, "agri_support_index": 140}, "horizon_years": 10}'
        with patch.object(llm, "_call_json", return_value=response):
            result = llm.parse_policy_intent("raise GST")

        self.assertEqual(result, {"policy_inputs": {"gst_rate": 20}, "horizon_years": 10})

    def test_json_uses_gemini_before_groq(self) -> None:
        with patch.object(llm, "_call_gemini", return_value='{"ok": true}') as gemini:
            with patch.object(llm, "_call_groq") as groq:
                result = llm._call_json([])

        self.assertEqual(result, '{"ok": true}')
        gemini.assert_called_once()
        groq.assert_not_called()

    def test_json_falls_back_to_groq_after_gemini_error(self) -> None:
        with patch.object(llm, "_call_gemini", return_value="LLM Integration Error: unavailable"):
            with patch.object(llm, "_call_groq", return_value='{"ok": true}') as groq:
                result = llm._call_json([])

        self.assertEqual(result, '{"ok": true}')
        groq.assert_called_once()

    def test_parser_uses_local_policy_fallback(self) -> None:
        with patch.object(llm, "_call_json", return_value="LLM Integration Error: unavailable"):
            result = llm.parse_policy_intent("Increase infrastructure spending by 20% over 10 years")

        self.assertEqual(result["horizon_years"], 10)
        self.assertEqual(result["policy_inputs"]["infrastructure_push_index"], 120.0)

    def test_parser_local_fallback_handles_rate_cuts(self) -> None:
        with patch.object(llm, "_call_json", side_effect=ValueError("bad json")):
            result = llm.parse_policy_intent("Cut GST by 2 percentage points")

        self.assertEqual(result["policy_inputs"]["gst_rate"], 16.0)

    def test_chat_response_has_local_fallback_when_llm_is_unavailable(self) -> None:
        payload = {
            "economic": {
                "headline": "Growth improves while inflation rises.",
                "macro_metrics": [
                    {"label": "GDP growth", "delta": 1.2, "unit": "%"},
                    {"label": "Inflation", "delta": 0.8, "unit": "%"},
                ],
                "confidence": {"score": 85, "notes": "Good"},
            },
            "risk": {
                "risk_level": "moderate",
                "flagged_risks": ["Moderate inflationary trend"],
                "trade_offs": ["Growth is accelerating, but at the cost of higher inflation."],
            },
            "evidence": {"citations": [{"title": "Inflation outlook"}]},
        }
        with patch.object(llm, "_call_text", return_value="LLM Integration Error: unavailable"):
            result = llm.generate_chat_response("What changes?", payload)

        self.assertIn("Scenario Brief", result)
        self.assertIn("Growth improves while inflation rises.", result)
        self.assertIn("Moderate inflationary trend", result)
        self.assertIn("Inflation outlook", result)


if __name__ == "__main__":
    unittest.main()
