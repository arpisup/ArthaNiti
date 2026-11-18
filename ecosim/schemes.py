from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ecosim.profiler import UserProfile


@dataclass(frozen=True)
class SchemeEligibility:
    """Structured eligibility criteria for a government scheme."""

    age_min: int | None = None
    age_max: int | None = None
    income_max: float | None = None
    occupations: list[str] = field(default_factory=list)
    states: str | list[str] = "all"
    gender: str | None = None
    area: str | None = None
    additional_conditions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SchemeBenefits:
    """Structured benefit description for a government scheme."""

    type: str = ""
    amount_annual: float | None = None
    description: str = ""


@dataclass(frozen=True)
class Scheme:
    """Represents a single government scheme with all metadata."""

    scheme_id: str
    name: str
    ministry: str
    category: str
    policy_type: str
    government_level: str
    target_group: list[str]
    eligibility: SchemeEligibility
    benefits: SchemeBenefits
    economic_sector: str
    related_indicators: list[str]
    related_levers: list[str]
    source_url: str
    start_date: str | None = None
    end_date: str | None = None
    active: bool = True


@dataclass
class SchemeMatch:
    """Result of matching a user profile against a scheme."""

    scheme: Scheme
    eligible: bool
    relevance_score: float
    match_reasons: list[str]
    disqualify_reasons: list[str]


def _parse_eligibility(raw: dict[str, Any]) -> SchemeEligibility:
    """Parse raw eligibility JSON into a structured object."""
    occupations = raw.get("occupations") or []
    if occupations is None:
        occupations = []
    return SchemeEligibility(
        age_min=raw.get("age_min"),
        age_max=raw.get("age_max"),
        income_max=raw.get("income_max"),
        occupations=occupations,
        states=raw.get("states", "all"),
        gender=raw.get("gender"),
        area=raw.get("area"),
        additional_conditions=raw.get("additional_conditions") or [],
    )


def _parse_benefits(raw: dict[str, Any]) -> SchemeBenefits:
    """Parse raw benefits JSON into a structured object."""
    return SchemeBenefits(
        type=raw.get("type", ""),
        amount_annual=raw.get("amount_annual"),
        description=raw.get("description", ""),
    )


def _parse_scheme(raw: dict[str, Any]) -> Scheme:
    """Parse a single raw scheme JSON entry into a Scheme object."""
    return Scheme(
        scheme_id=raw["scheme_id"],
        name=raw["name"],
        ministry=raw.get("ministry", ""),
        category=raw.get("category", ""),
        policy_type=raw.get("policy_type", ""),
        government_level=raw.get("government_level", "central"),
        target_group=raw.get("target_group", []),
        eligibility=_parse_eligibility(raw.get("eligibility", {})),
        benefits=_parse_benefits(raw.get("benefits", {})),
        economic_sector=raw.get("economic_sector", "general"),
        related_indicators=raw.get("related_indicators", []),
        related_levers=raw.get("related_levers", []),
        source_url=raw.get("source_url", ""),
        start_date=raw.get("start_date"),
        end_date=raw.get("end_date"),
        active=raw.get("active", True),
    )


def load_schemes(base_dir: Path) -> list[Scheme]:
    """Load the scheme database from configs/schemes.json.

    Returns a list of Scheme objects, filtered to only active schemes.
    """
    path = base_dir / "configs" / "schemes.json"
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    schemes = [_parse_scheme(entry) for entry in payload.get("schemes", [])]
    return [scheme for scheme in schemes if scheme.active]


def _check_age(profile: UserProfile, eligibility: SchemeEligibility) -> tuple[bool, str | None]:
    """Check if the user's age falls within the scheme's age range."""
    if eligibility.age_min is not None and profile.age < eligibility.age_min:
        return False, f"Age {profile.age} is below minimum {eligibility.age_min}"
    if eligibility.age_max is not None and profile.age > eligibility.age_max:
        return False, f"Age {profile.age} is above maximum {eligibility.age_max}"
    return True, None


def _check_income(profile: UserProfile, eligibility: SchemeEligibility) -> tuple[bool, str | None]:
    """Check if the user's income is within the scheme's income limit."""
    if eligibility.income_max is not None and profile.annual_income > eligibility.income_max:
        return False, f"Income ₹{profile.annual_income:,.0f} exceeds limit ₹{eligibility.income_max:,.0f}"
    return True, None


def _check_occupation(profile: UserProfile, eligibility: SchemeEligibility) -> tuple[bool, str | None]:
    """Check if the user's occupation matches the scheme's occupation requirements."""
    if not eligibility.occupations:
        return True, None

    user_occupation = profile.occupation.lower().strip()
    allowed = [occ.lower().strip() for occ in eligibility.occupations]

    if user_occupation in allowed:
        return True, None

    # Flexible matching: check partial matches
    for allowed_occ in allowed:
        if allowed_occ in user_occupation or user_occupation in allowed_occ:
            return True, None

    return False, f"Occupation '{profile.occupation}' not in {eligibility.occupations}"


def _check_state(profile: UserProfile, eligibility: SchemeEligibility) -> tuple[bool, str | None]:
    """Check if the user's state is covered by the scheme."""
    if eligibility.states == "all":
        return True, None
    if isinstance(eligibility.states, list):
        user_state = profile.state.lower().strip()
        allowed_states = [s.lower().strip() for s in eligibility.states]
        if user_state in allowed_states:
            return True, None
        return False, f"State '{profile.state}' not covered by this scheme"
    return True, None


def _check_gender(profile: UserProfile, eligibility: SchemeEligibility) -> tuple[bool, str | None]:
    """Check if the user's gender matches the scheme's gender requirement."""
    if eligibility.gender is None:
        return True, None
    if profile.gender is None:
        # If no gender specified by user but scheme requires one, soft pass
        return True, None
    if profile.gender.lower() != eligibility.gender.lower():
        return False, f"Scheme is for {eligibility.gender} only"
    return True, None


def _check_area(profile: UserProfile, eligibility: SchemeEligibility) -> tuple[bool, str | None]:
    """Check if the user's area (urban/rural) matches the scheme."""
    if eligibility.area is None or eligibility.area == "both":
        return True, None
    user_area = profile.area.lower().strip()
    scheme_area = eligibility.area.lower().strip()
    if user_area == scheme_area:
        return True, None
    return False, f"Scheme is for {eligibility.area} areas only"


def _target_group_match_score(profile: UserProfile, target_group: list[str]) -> float:
    """Score how well the user's profile matches the scheme's target group.

    Returns a score between 0.0 and 1.0.
    """
    if not target_group:
        return 0.5

    user_traits: set[str] = set()

    # Income group
    if profile.annual_income < 300_000:
        user_traits.add("low_income")
        user_traits.add("workers")
    elif profile.annual_income <= 1_200_000:
        user_traits.add("middle_income")
        user_traits.add("workers")
    else:
        user_traits.add("entrepreneurs")

    # Occupation
    occupation = profile.occupation.lower()
    if occupation == "farmer":
        user_traits.add("farmers")
    elif occupation in ("student",):
        user_traits.add("students")
        user_traits.add("youth")
    elif occupation == "business_owner":
        user_traits.add("msme_owners")
        user_traits.add("entrepreneurs")
    elif occupation == "daily_wage":
        user_traits.add("workers")
        user_traits.add("low_income")

    # Age groups
    if profile.age < 35:
        user_traits.add("youth")
    if profile.age >= 60:
        user_traits.add("senior_citizens")

    # Gender
    if profile.gender and profile.gender.lower() == "female":
        user_traits.add("women")

    # Business
    if profile.is_business_owner:
        user_traits.add("msme_owners")
        user_traits.add("entrepreneurs")

    user_traits.add("general")

    target_set = {t.lower().strip() for t in target_group}
    overlap = user_traits & target_set

    if "general" in target_set and len(target_set) == 1:
        return 0.4

    if overlap - {"general"}:
        return min(1.0, len(overlap) / len(target_set))

    if "general" in overlap:
        return 0.3

    return 0.0


def scheme_relevance_score(profile: UserProfile, scheme: Scheme) -> float:
    """Compute an overall relevance score (0.0 to 1.0) for a scheme.

    Combines eligibility checks with target-group alignment and
    economic-sector relevance.
    """
    score = 0.0

    # Target group match (up to 0.5)
    tg_score = _target_group_match_score(profile, scheme.target_group)
    score += tg_score * 0.5

    # Sector alignment (up to 0.2)
    user_sector = profile.sector.lower()
    scheme_sector = scheme.economic_sector.lower()
    if user_sector == scheme_sector:
        score += 0.2
    elif scheme_sector == "general":
        score += 0.1

    # Income relevance (up to 0.15)
    elig = scheme.eligibility
    if elig.income_max is not None:
        if profile.annual_income <= elig.income_max:
            # The closer to the limit, the more relevant
            income_ratio = profile.annual_income / elig.income_max
            score += 0.15 * (1.0 - income_ratio * 0.3)
        else:
            score -= 0.1

    # Benefit value signal (up to 0.15)
    if scheme.benefits.amount_annual and scheme.benefits.amount_annual > 0:
        # Higher benefit relative to income = more relevant
        if profile.annual_income > 0:
            benefit_ratio = min(scheme.benefits.amount_annual / profile.annual_income, 1.0)
            score += benefit_ratio * 0.15
        else:
            score += 0.15

    return round(max(0.0, min(1.0, score)), 3)


def match_single_scheme(profile: UserProfile, scheme: Scheme) -> SchemeMatch:
    """Evaluate a single scheme against a user profile.

    Returns a SchemeMatch with eligibility status, relevance score,
    match reasons, and disqualification reasons.
    """
    checks = [
        _check_age(profile, scheme.eligibility),
        _check_income(profile, scheme.eligibility),
        _check_occupation(profile, scheme.eligibility),
        _check_state(profile, scheme.eligibility),
        _check_gender(profile, scheme.eligibility),
        _check_area(profile, scheme.eligibility),
    ]

    disqualify_reasons: list[str] = []
    for passed, reason in checks:
        if not passed and reason:
            disqualify_reasons.append(reason)

    eligible = len(disqualify_reasons) == 0

    # Build match reasons
    match_reasons: list[str] = []
    if eligible:
        tg_score = _target_group_match_score(profile, scheme.target_group)
        if tg_score > 0.5:
            match_reasons.append("Strong target-group alignment")
        elif tg_score > 0.2:
            match_reasons.append("Partial target-group alignment")

        if scheme.benefits.amount_annual and scheme.benefits.amount_annual > 0:
            match_reasons.append(f"Potential annual benefit: ₹{scheme.benefits.amount_annual:,.0f}")

        if scheme.benefits.description:
            match_reasons.append(scheme.benefits.description)

    relevance = scheme_relevance_score(profile, scheme) if eligible else 0.0

    return SchemeMatch(
        scheme=scheme,
        eligible=eligible,
        relevance_score=relevance,
        match_reasons=match_reasons,
        disqualify_reasons=disqualify_reasons,
    )


def match_schemes(
    profile: UserProfile,
    schemes: list[Scheme],
    eligible_only: bool = True,
    min_relevance: float = 0.0,
) -> list[SchemeMatch]:
    """Match a user profile against all schemes and return sorted results.

    Args:
        profile: The user's profile.
        schemes: List of all available schemes.
        eligible_only: If True, only return schemes the user is eligible for.
        min_relevance: Minimum relevance score threshold (0.0 to 1.0).

    Returns:
        List of SchemeMatch objects, sorted by relevance score descending.
    """
    matches: list[SchemeMatch] = []
    for scheme in schemes:
        match = match_single_scheme(profile, scheme)
        if eligible_only and not match.eligible:
            continue
        if match.relevance_score < min_relevance:
            continue
        matches.append(match)

    matches.sort(key=lambda m: m.relevance_score, reverse=True)
    return matches


def scheme_match_payload(matches: list[SchemeMatch]) -> list[dict[str, Any]]:
    """Convert scheme matches to a JSON-serializable payload for the API.

    Returns a list of scheme match dictionaries suitable for API responses.
    """
    results: list[dict[str, Any]] = []
    for match in matches:
        scheme = match.scheme
        results.append({
            "scheme_id": scheme.scheme_id,
            "name": scheme.name,
            "ministry": scheme.ministry,
            "category": scheme.category,
            "government_level": scheme.government_level,
            "economic_sector": scheme.economic_sector,
            "eligible": match.eligible,
            "relevance_score": match.relevance_score,
            "match_reasons": match.match_reasons,
            "disqualify_reasons": match.disqualify_reasons,
            "benefits": {
                "type": scheme.benefits.type,
                "amount_annual": scheme.benefits.amount_annual,
                "description": scheme.benefits.description,
            },
            "target_group": scheme.target_group,
            "source_url": scheme.source_url,
            "related_indicators": scheme.related_indicators,
            "related_levers": scheme.related_levers,
        })
    return results
