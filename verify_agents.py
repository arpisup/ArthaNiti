import json
from pathlib import Path
from ecosim.service import EcoSimService
from ecosim.agents import AnalysisContext, EconomicAgent, CitizenAgent, PolicyAgent, RiskAgent, EvidenceAgent

print('--- INITIALIZING AGENTS ---')
print('EconomicAgent:', EconomicAgent().description)
print('CitizenAgent:', CitizenAgent().description)
print('PolicyAgent:', PolicyAgent().description)
print('RiskAgent:', RiskAgent().description)
print('EvidenceAgent:', EvidenceAgent().description)
print('\n--- RUNNING E2E MULTI-AGENT ORCHESTRATION ---')

service = EcoSimService(Path('.'))
payload = {
    'user_profile': {
        'age': 28, 'state': 'Tamil Nadu', 'annual_income': 180000,
        'occupation': 'farmer', 'employment_status': 'self_employed',
        'sector': 'agriculture', 'area': 'rural', 'family_size': 5
    },
    'policy_inputs': {'welfare_spending_index': 120, 'agri_support_index': 115},
    'horizon_years': 3
}

print('User Profile:', payload['user_profile']['occupation'], 'in', payload['user_profile']['state'])
print('Policy Action:', payload['policy_inputs'])

res = service.multi_agent_assess_payload(payload)

print('\n--- AGENT 1: EconomicAgent Output ---')
print('Macro Status:', res['economic']['overall_macro_status'])
print('Headline:', res['economic']['headline'])
print('Top 3 Macro Metrics:', [m['id'] for m in res['economic']['macro_metrics'][:3]])

print('\n--- AGENT 2: CitizenAgent Output ---')
print('Dominant Persona:', res['citizen']['dominant_persona'])
print('Overall Personal Status:', res['citizen']['overall_status'])
print('Personalized Headline:', res['citizen']['headline'])

print('\n--- AGENT 3: PolicyAgent Output ---')
print(f"Evaluated {res['policy']['total_schemes_evaluated']} schemes.")
print(f"Matched {res['policy']['matched_scheme_count']} eligible schemes.")
print('Top 3 Schemes:', [s['name'] for s in res['policy']['matched_schemes'][:3]])

print('\n--- AGENT 4: RiskAgent Output ---')
print('Risk Level:', res['risk']['risk_level'])
print('Flagged Risks:', res['risk']['flagged_risks'])

print('\n--- AGENT 5: EvidenceAgent Output ---')
print('Knowledge Base Query Used:', res['evidence']['query'])
print('Citations Found:', len(res['evidence']['citations']))
