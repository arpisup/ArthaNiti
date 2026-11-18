import unittest
from ecosim.profiler import (
    UserProfile,
    parse_user_profile,
    profile_to_persona_weights,
    compute_macro_exposure,
    personalized_impact,
    profile_summary
)

class TestProfiler(unittest.TestCase):
    def test_parse_user_profile_valid(self):
        data = {
            'age': 30,
            'state': 'Maharashtra',
            'annual_income': 500000,
            'occupation': 'software_engineer',
            'employment_status': 'employed'
        }
        profile = parse_user_profile(data)
        self.assertEqual(profile.age, 30)
        self.assertEqual(profile.annual_income, 500000)
        self.assertEqual(profile.country, 'India')
        self.assertEqual(profile.family_size, 4)

    def test_parse_user_profile_invalid_missing(self):
        data = {'state': 'Goa', 'annual_income': 1000}
        with self.assertRaises(ValueError) as context:
            parse_user_profile(data)
        self.assertIn("Missing required key", str(context.exception))

    def test_parse_user_profile_invalid_age(self):
        data = {
            'age': -5,
            'state': 'Maharashtra',
            'annual_income': 500000,
            'occupation': 'software_engineer',
            'employment_status': 'employed'
        }
        with self.assertRaises(ValueError):
            parse_user_profile(data)

    def test_parse_user_profile_invalid_income(self):
        data = {
            'age': 30,
            'state': 'Maharashtra',
            'annual_income': -5000,
            'occupation': 'software_engineer',
            'employment_status': 'employed'
        }
        with self.assertRaises(ValueError):
            parse_user_profile(data)

    def test_persona_weights_farmer(self):
        profile = UserProfile(
            age=40, state='Punjab', annual_income=250000,
            occupation='farmer', employment_status='self_employed',
            sector='agriculture', area='rural'
        )
        weights = profile_to_persona_weights(profile)
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=4)
        self.assertGreater(weights['farmers'], 0)
        self.assertGreater(weights['lig_households'], 0)

    def test_persona_weights_hig_business(self):
        profile = UserProfile(
            age=50, state='Gujarat', annual_income=2000000,
            occupation='business_owner', employment_status='self_employed',
            is_business_owner=True
        )
        weights = profile_to_persona_weights(profile)
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=4)
        self.assertGreater(weights['hig_households'], 0)
        self.assertGreater(weights['msmes'], 0)

    def test_macro_exposure(self):
        profile = UserProfile(
            age=22, state='Delhi', annual_income=150000,
            occupation='student', employment_status='unemployed',
            family_size=6
        )
        exposures = compute_macro_exposure(profile)
        self.assertEqual(exposures['unemployment_pct'], 90.0)
        self.assertEqual(exposures['inflation_pct'], 90.0)
        self.assertEqual(exposures['household_pressure_index'], 100.0)

    def test_personalized_impact(self) -> None:
        profile = UserProfile(
            age=35, state='Karnataka', annual_income=800000,
            occupation='clerk', employment_status='employed'
        )
        weights = profile_to_persona_weights(profile)
        
        simulation_result = {
            "entities": [
                {
                    "id": "mig_households",
                    "metrics": [{"id": "savings", "value": 100}, {"id": "stress", "value": 50}]
                },
                {
                    "id": "market_activity",
                    "metrics": [{"id": "savings", "value": 10}, {"id": "stress", "value": 10}]
                }
            ]
        }
        
        impact = personalized_impact(simulation_result, weights)
        self.assertIn('blended_metrics', impact)
        self.assertIn('dominant_persona', impact)
        self.assertEqual(impact['dominant_persona'], 'mig_households')
        self.assertGreater(impact['blended_metrics']['savings'], 0)

    def test_profile_summary(self):
        profile = UserProfile(
            age=65, state='Kerala', annual_income=0,
            occupation='retired', employment_status='unemployed'
        )
        summary = profile_summary(profile)
        self.assertEqual(summary['income_bracket'], 'LIG')
        self.assertEqual(summary['demographic_features']['age'], 65)

if __name__ == '__main__':
    unittest.main()
