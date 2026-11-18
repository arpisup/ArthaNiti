"""Multi-agent system for economic policy impact assessment.

This package provides specialized agents that independently analyze
different dimensions of a policy scenario, coordinated by an
orchestrator that merges their assessments into a unified result.

Agents:
    EconomicAgent   — national-level macro impact assessment
    CitizenAgent    — individual-level impact based on user profile
    PolicyAgent     — government scheme discovery and eligibility
    EvidenceAgent   — knowledge retrieval and citation support
    RiskAgent       — risk identification and trade-off analysis
    Orchestrator    — coordinates all agents and merges outputs
"""

from ecosim.agents.base import AnalysisContext, BaseAgent
from ecosim.agents.economic_agent import EconomicAgent
from ecosim.agents.citizen_agent import CitizenAgent
from ecosim.agents.policy_agent import PolicyAgent
from ecosim.agents.evidence_agent import EvidenceAgent
from ecosim.agents.risk_agent import RiskAgent
from ecosim.agents.orchestrator import Orchestrator

__all__ = [
    "AnalysisContext",
    "BaseAgent",
    "EconomicAgent",
    "CitizenAgent",
    "PolicyAgent",
    "EvidenceAgent",
    "RiskAgent",
    "Orchestrator",
]
