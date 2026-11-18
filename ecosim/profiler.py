from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Any, Optional

INDIAN_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
    "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram",
    "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
    "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal"
]

@dataclass
class UserProfile:
    """User profile for economic simulation."""
    age: int
    state: str
    annual_income: float
    occupation: str
    employment_status: str
    country: str = 'India'
    family_size: int = 4
    sector: str = 'services'
    is_business_owner: bool = False
    area: str = 'urban'
    gender: Optional[str] = None


def parse_user_profile(data: Dict[str, Any]) -> UserProfile:
    """Validates and creates a UserProfile from raw input data."""
    required_keys = ['age', 'state', 'annual_income', 'occupation', 'employment_status']
    for k in required_keys:
        if k not in data:
            raise ValueError(f"Missing required key: {k}")
            
    age = int(data['age'])
    if age < 0 or age > 120:
        raise ValueError("Age must be between 0 and 120")
        
    state = str(data['state'])
    
    annual_income = float(data['annual_income'])
    if annual_income < 0:
        raise ValueError("Income cannot be negative")
        
    return UserProfile(
        age=age,
        state=state,
        annual_income=annual_income,
        occupation=str(data['occupation']),
        employment_status=str(data['employment_status']),
        country=data.get('country', 'India'),
        family_size=int(data.get('family_size', 4)),
        sector=data.get('sector', 'services'),
        is_business_owner=bool(data.get('is_business_owner', False)),
        area=data.get('area', 'urban'),
        gender=data.get('gender', None)
    )


def profile_to_persona_weights(profile: UserProfile) -> Dict[str, float]:
    """Maps user attributes to a weighted blend of 7 personas."""
    weights = {
        'lig_households': 0.0,
        'mig_households': 0.0,
        'hig_households': 0.0,
        'farmers': 0.0,
        'msmes': 0.0,
        'public_services': 0.0,
        'market_activity': 0.1  # baseline exposure
    }
    
    # 1. Income bracket
    if profile.annual_income < 300000:
        weights['lig_households'] += 0.5
    elif profile.annual_income <= 1200000:
        weights['mig_households'] += 0.5
    else:
        weights['hig_households'] += 0.5
        
    # 2. Occupation & Sector
    if profile.occupation.lower() == 'farmer' or profile.sector.lower() == 'agriculture':
        weights['farmers'] += 0.4
    
    if profile.is_business_owner or profile.occupation.lower() == 'business_owner':
        weights['msmes'] += 0.4
        
    if profile.sector.lower() == 'government':
        weights['public_services'] += 0.3
        
    # 3. Area boosts
    if profile.area.lower() == 'rural' and weights['farmers'] > 0:
        weights['farmers'] += 0.1
        
    # Normalize weights to sum to 1.0
    total_weight = sum(weights.values())
    if total_weight > 0:
        for k in weights:
            weights[k] = round(weights[k] / total_weight, 4)
            
    # Fix small rounding errors
    diff = 1.0 - sum(weights.values())
    weights['market_activity'] += diff
    weights['market_activity'] = round(weights['market_activity'], 4)
    
    return weights


def compute_macro_exposure(profile: UserProfile) -> Dict[str, float]:
    """Scores 0-100 how exposed the user is to each macro metric."""
    exposures = {
        'inflation_pct': 50.0,
        'unemployment_pct': 50.0,
        'gdp_growth_pct': 50.0,
        'fiscal_stress_index': 50.0,
        'investment_sentiment_index': 50.0,
        'household_pressure_index': 50.0,
        'trade_momentum_index': 50.0,
        'exchange_stability_index': 50.0
    }
    
    # Inflation exposure
    if profile.annual_income < 300000:
        exposures['inflation_pct'] = 90.0
    elif profile.annual_income <= 1200000:
        exposures['inflation_pct'] = 70.0
    else:
        exposures['inflation_pct'] = 40.0
        
    if profile.occupation in ['farmer', 'daily_wage']:
        exposures['inflation_pct'] = min(100.0, exposures['inflation_pct'] + 10)
        
    # Unemployment
    if profile.age < 25 or profile.occupation in ['student', 'unemployed']:
        exposures['unemployment_pct'] = 90.0
        
    # GDP Growth
    if profile.is_business_owner:
        exposures['gdp_growth_pct'] = 80.0
        
    # Fiscal Stress
    if profile.sector == 'government':
        exposures['fiscal_stress_index'] = 85.0
        
    # Investment Sentiment
    if profile.annual_income > 1200000 or profile.is_business_owner:
        exposures['investment_sentiment_index'] = 80.0
        
    # Household Pressure
    if profile.annual_income < 300000:
        exposures['household_pressure_index'] = 85.0
    if profile.family_size > 4:
        exposures['household_pressure_index'] = min(100.0, exposures['household_pressure_index'] + 15)
        
    # Trade Momentum
    if profile.sector in ['manufacturing', 'exporters']:
        exposures['trade_momentum_index'] = 85.0
        
    return exposures


def personalized_impact(simulation_result: Dict[str, Any], persona_weights: Dict[str, float]) -> Dict[str, Any]:
    """Blends simulation metrics based on user persona weights."""
    entities = simulation_result.get('entities', [])
    blended_metrics = {}
    total_weight = 0.0
    
    dominant_persona = max(persona_weights.items(), key=lambda x: x[1])[0]
    
    for entity in entities:
        eid = entity.get('id')
        if eid in persona_weights and persona_weights[eid] > 0:
            w = persona_weights[eid]
            total_weight += w
            for metric_obj in entity.get('metrics', []):
                k = metric_obj.get('id')
                v = metric_obj.get('value', 0.0)
                if k and isinstance(v, (int, float)):
                    blended_metrics[k] = blended_metrics.get(k, 0.0) + (v * w)
                    
    # Normalize metrics if total_weight < 1 (due to missing personas in simulation result)
    if total_weight > 0:
        for k in blended_metrics:
            blended_metrics[k] = blended_metrics[k] / total_weight
            
    headline = f"Impact highly influenced by {dominant_persona}"
    
    return {
        'blended_metrics': blended_metrics,
        'dominant_persona': dominant_persona,
        'overall_status': 'mixed',
        'headline': headline
    }


def profile_summary(profile: UserProfile) -> Dict[str, Any]:
    """Returns a structured summary of the profile."""
    if profile.annual_income < 300000:
        income_bracket = 'LIG'
    elif profile.annual_income <= 1200000:
        income_bracket = 'MIG'
    else:
        income_bracket = 'HIG'
        
    return {
        'income_bracket': income_bracket,
        'demographic_features': {
            'age': profile.age,
            'state': profile.state,
            'area': profile.area,
            'family_size': profile.family_size
        },
        'economic_features': {
            'annual_income': profile.annual_income,
            'occupation': profile.occupation,
            'employment_status': profile.employment_status,
            'sector': profile.sector,
            'is_business_owner': profile.is_business_owner
        }
    }
