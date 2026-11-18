from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ecosim.profiler import UserProfile
from ecosim.schemes import (
    Scheme,
    SchemeEligibility,
    SchemeBenefits,
    SchemeMatch,
    _check_age,
    _check_income,
    _check_occupation,
    _check_state,
    _check_gender,
    _check_area,
    _target_group_match_score,
    load_schemes,
    match_single_scheme,
    match_schemes,
    scheme_relevance_score,
    scheme_match_payload,
)


def _make_profile(**overrides: object) -> UserProfile:
    """Create a test profile with sensible defaults, overriding as needed."""
    defaults = {
        "age": 30,
        "state": "Tamil Nadu",
        "annual_income": 500_000.0,
        "occupation": "salaried",
        "employment_status": "employed",
        "country": "India",
        "family_size": 4,
        "sector": "services",
        "is_business_owner": False,
        "area": "urban",
        "gender": None,
    }
    defaults.update(overrides)
    return UserProfile(**defaults)


def _make_scheme(**overrides: object) -> Scheme:
    """Create a test scheme with sensible defaults, overriding as needed."""
    defaults = {
        "scheme_id": "test_scheme",
        "name": "Test Scheme",
        "ministry": "Test Ministry",
        "category": "subsidy",
        "policy_type": "welfare",
        "government_level": "central",
        "target_group": ["general"],
        "eligibility": SchemeEligibility(),
        "benefits": SchemeBenefits(type="cash_transfer", amount_annual=6000, description="Test benefit"),
        "economic_sector": "general",
        "related_indicators": ["gdp_growth_pct"],
        "related_levers": ["welfare_spending_index"],
        "source_url": "https://example.gov.in",
        "active": True,
    }
    defaults.update(overrides)
    return Scheme(**defaults)


class TestEligibilityChecks(unittest.TestCase):
    """Tests for individual eligibility check functions."""

    def test_age_within_range(self) -> None:
        profile = _make_profile(age=25)
        elig = SchemeEligibility(age_min=18, age_max=35)
        passed, reason = _check_age(profile, elig)
        self.assertTrue(passed)
        self.assertIsNone(reason)

    def test_age_below_minimum(self) -> None:
        profile = _make_profile(age=16)
        elig = SchemeEligibility(age_min=18, age_max=35)
        passed, reason = _check_age(profile, elig)
        self.assertFalse(passed)
        self.assertIn("below minimum", reason)

    def test_age_above_maximum(self) -> None:
        profile = _make_profile(age=40)
        elig = SchemeEligibility(age_min=18, age_max=35)
        passed, reason = _check_age(profile, elig)
        self.assertFalse(passed)
        self.assertIn("above maximum", reason)

    def test_age_no_limits(self) -> None:
        profile = _make_profile(age=99)
        elig = SchemeEligibility()
        passed, _ = _check_age(profile, elig)
        self.assertTrue(passed)

    def test_income_within_limit(self) -> None:
        profile = _make_profile(annual_income=200_000)
        elig = SchemeEligibility(income_max=500_000)
        passed, _ = _check_income(profile, elig)
        self.assertTrue(passed)

    def test_income_exceeds_limit(self) -> None:
        profile = _make_profile(annual_income=600_000)
        elig = SchemeEligibility(income_max=500_000)
        passed, reason = _check_income(profile, elig)
        self.assertFalse(passed)
        self.assertIn("exceeds", reason)

    def test_income_no_limit(self) -> None:
        profile = _make_profile(annual_income=10_000_000)
        elig = SchemeEligibility()
        passed, _ = _check_income(profile, elig)
        self.assertTrue(passed)

    def test_occupation_match(self) -> None:
        profile = _make_profile(occupation="farmer")
        elig = SchemeEligibility(occupations=["farmer", "daily_wage"])
        passed, _ = _check_occupation(profile, elig)
        self.assertTrue(passed)

    def test_occupation_no_match(self) -> None:
        profile = _make_profile(occupation="salaried")
        elig = SchemeEligibility(occupations=["farmer"])
        passed, reason = _check_occupation(profile, elig)
        self.assertFalse(passed)
        self.assertIn("not in", reason)

    def test_occupation_no_restriction(self) -> None:
        profile = _make_profile(occupation="anything")
        elig = SchemeEligibility(occupations=[])
        passed, _ = _check_occupation(profile, elig)
        self.assertTrue(passed)

    def test_state_all(self) -> None:
        profile = _make_profile(state="Tamil Nadu")
        elig = SchemeEligibility(states="all")
        passed, _ = _check_state(profile, elig)
        self.assertTrue(passed)

    def test_state_specific_match(self) -> None:
        profile = _make_profile(state="Tamil Nadu")
        elig = SchemeEligibility(states=["Tamil Nadu", "Kerala"])
        passed, _ = _check_state(profile, elig)
        self.assertTrue(passed)

    def test_state_specific_no_match(self) -> None:
        profile = _make_profile(state="Bihar")
        elig = SchemeEligibility(states=["Tamil Nadu", "Kerala"])
        passed, reason = _check_state(profile, elig)
        self.assertFalse(passed)
        self.assertIn("not covered", reason)

    def test_gender_no_restriction(self) -> None:
        profile = _make_profile(gender="male")
        elig = SchemeEligibility()
        passed, _ = _check_gender(profile, elig)
        self.assertTrue(passed)

    def test_gender_match(self) -> None:
        profile = _make_profile(gender="female")
        elig = SchemeEligibility(gender="female")
        passed, _ = _check_gender(profile, elig)
        self.assertTrue(passed)

    def test_gender_no_match(self) -> None:
        profile = _make_profile(gender="male")
        elig = SchemeEligibility(gender="female")
        passed, reason = _check_gender(profile, elig)
        self.assertFalse(passed)
        self.assertIn("female only", reason)

    def test_area_match(self) -> None:
        profile = _make_profile(area="rural")
        elig = SchemeEligibility(area="rural")
        passed, _ = _check_area(profile, elig)
        self.assertTrue(passed)

    def test_area_no_match(self) -> None:
        profile = _make_profile(area="urban")
        elig = SchemeEligibility(area="rural")
        passed, reason = _check_area(profile, elig)
        self.assertFalse(passed)
        self.assertIn("rural areas only", reason)


class TestTargetGroupMatching(unittest.TestCase):
    """Tests for target group match scoring."""

    def test_farmer_matches_farmers_group(self) -> None:
        profile = _make_profile(occupation="farmer", annual_income=200_000)
        score = _target_group_match_score(profile, ["farmers", "low_income"])
        self.assertGreater(score, 0.5)

    def test_student_matches_youth(self) -> None:
        profile = _make_profile(age=20, occupation="student")
        score = _target_group_match_score(profile, ["youth", "students"])
        self.assertGreater(score, 0.5)

    def test_senior_matches_senior_group(self) -> None:
        profile = _make_profile(age=65, occupation="retired")
        score = _target_group_match_score(profile, ["senior_citizens"])
        self.assertGreater(score, 0.5)

    def test_general_only_low_score(self) -> None:
        profile = _make_profile()
        score = _target_group_match_score(profile, ["general"])
        self.assertLessEqual(score, 0.5)

    def test_no_target_group(self) -> None:
        profile = _make_profile()
        score = _target_group_match_score(profile, [])
        self.assertEqual(score, 0.5)

    def test_business_owner_matches_msme(self) -> None:
        profile = _make_profile(is_business_owner=True, annual_income=1_500_000)
        score = _target_group_match_score(profile, ["msme_owners", "entrepreneurs"])
        self.assertGreater(score, 0.5)


class TestSchemeMatching(unittest.TestCase):
    """Tests for full scheme matching logic."""

    def test_eligible_scheme(self) -> None:
        profile = _make_profile(age=25, annual_income=200_000)
        scheme = _make_scheme(
            eligibility=SchemeEligibility(age_min=18, age_max=60, income_max=500_000),
            target_group=["low_income", "workers"],
        )
        match = match_single_scheme(profile, scheme)
        self.assertTrue(match.eligible)
        self.assertGreater(match.relevance_score, 0.0)
        self.assertEqual(len(match.disqualify_reasons), 0)

    def test_ineligible_age(self) -> None:
        profile = _make_profile(age=70)
        scheme = _make_scheme(
            eligibility=SchemeEligibility(age_max=60),
        )
        match = match_single_scheme(profile, scheme)
        self.assertFalse(match.eligible)
        self.assertEqual(match.relevance_score, 0.0)
        self.assertGreater(len(match.disqualify_reasons), 0)

    def test_ineligible_income(self) -> None:
        profile = _make_profile(annual_income=1_000_000)
        scheme = _make_scheme(
            eligibility=SchemeEligibility(income_max=500_000),
        )
        match = match_single_scheme(profile, scheme)
        self.assertFalse(match.eligible)

    def test_match_schemes_returns_sorted(self) -> None:
        profile = _make_profile(age=25, occupation="farmer", annual_income=150_000, area="rural")
        schemes = [
            _make_scheme(
                scheme_id="s1",
                target_group=["general"],
                eligibility=SchemeEligibility(),
            ),
            _make_scheme(
                scheme_id="s2",
                target_group=["farmers", "low_income"],
                eligibility=SchemeEligibility(),
                economic_sector="agriculture",
                benefits=SchemeBenefits(type="cash_transfer", amount_annual=6000, description="Cash"),
            ),
        ]
        matches = match_schemes(profile, schemes, eligible_only=True)
        self.assertEqual(len(matches), 2)
        self.assertEqual(matches[0].scheme.scheme_id, "s2")
        self.assertGreaterEqual(matches[0].relevance_score, matches[1].relevance_score)

    def test_match_schemes_filters_ineligible(self) -> None:
        profile = _make_profile(age=10)
        schemes = [
            _make_scheme(eligibility=SchemeEligibility(age_min=18)),
        ]
        matches = match_schemes(profile, schemes, eligible_only=True)
        self.assertEqual(len(matches), 0)

    def test_match_schemes_includes_ineligible_when_asked(self) -> None:
        profile = _make_profile(age=10)
        schemes = [
            _make_scheme(eligibility=SchemeEligibility(age_min=18)),
        ]
        matches = match_schemes(profile, schemes, eligible_only=False)
        self.assertEqual(len(matches), 1)
        self.assertFalse(matches[0].eligible)


class TestSchemeLoading(unittest.TestCase):
    """Tests for loading schemes from a JSON file."""

    def test_load_schemes_from_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            configs = base_dir / "configs"
            configs.mkdir()
            schemes_data = {
                "version": "1.0",
                "schemes": [
                    {
                        "scheme_id": "test_1",
                        "name": "Test Scheme 1",
                        "ministry": "Test",
                        "category": "subsidy",
                        "policy_type": "welfare",
                        "government_level": "central",
                        "target_group": ["general"],
                        "eligibility": {"age_min": 18},
                        "benefits": {"type": "cash", "description": "Test"},
                        "economic_sector": "general",
                        "related_indicators": [],
                        "related_levers": [],
                        "source_url": "",
                        "active": True,
                    },
                    {
                        "scheme_id": "test_inactive",
                        "name": "Inactive Scheme",
                        "active": False,
                    },
                ],
            }
            (configs / "schemes.json").write_text(json.dumps(schemes_data), encoding="utf-8")

            schemes = load_schemes(base_dir)
            self.assertEqual(len(schemes), 1)
            self.assertEqual(schemes[0].scheme_id, "test_1")

    def test_load_schemes_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            schemes = load_schemes(Path(tmpdir))
            self.assertEqual(len(schemes), 0)


class TestSchemePayload(unittest.TestCase):
    """Tests for the API payload serialization."""

    def test_payload_structure(self) -> None:
        profile = _make_profile()
        scheme = _make_scheme(scheme_id="pay_test", name="Payload Test")
        match = match_single_scheme(profile, scheme)
        payload = scheme_match_payload([match])
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["scheme_id"], "pay_test")
        self.assertIn("eligible", payload[0])
        self.assertIn("relevance_score", payload[0])
        self.assertIn("benefits", payload[0])
        self.assertIn("match_reasons", payload[0])


class TestRelevanceScore(unittest.TestCase):
    """Tests for relevance scoring logic."""

    def test_relevance_between_zero_and_one(self) -> None:
        profile = _make_profile()
        scheme = _make_scheme()
        score = scheme_relevance_score(profile, scheme)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_farmer_high_relevance_for_agriculture_scheme(self) -> None:
        profile = _make_profile(occupation="farmer", sector="agriculture", annual_income=150_000)
        scheme = _make_scheme(
            target_group=["farmers", "low_income"],
            economic_sector="agriculture",
            eligibility=SchemeEligibility(income_max=500_000),
            benefits=SchemeBenefits(type="cash_transfer", amount_annual=6000, description="Test"),
        )
        score = scheme_relevance_score(profile, scheme)
        self.assertGreater(score, 0.5)


if __name__ == "__main__":
    unittest.main()
