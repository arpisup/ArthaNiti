from __future__ import annotations

from typing import Any

from ecosim.agents.base import AnalysisContext, BaseAgent


class RiskAgent(BaseAgent):
    """Identifies economic and policy implementation risks.

    This agent analyzes both the macro simulation results and the user's
    personalized impact to flag specific structural vulnerabilities,
    inflationary pressures, or trade-offs in the scenario.

    Outputs:
        risk_level: overall risk assessment (low, moderate, high, critical)
        flagged_risks: list of specific risk strings
        trade_offs: list of identified policy trade-offs
    """

    @property
    def agent_id(self) -> str:
        return "risk_agent"

    @property
    def agent_name(self) -> str:
        return "Risk & Trade-off Agent"

    @property
    def description(self) -> str:
        return (
            "Identifies vulnerabilities, structural risks, and policy "
            "trade-offs in the economic scenario."
        )

    def analyze(self, context: AnalysisContext) -> dict[str, Any]:
        """Analyze macro and micro data for risks and trade-offs."""
        flagged_risks: list[str] = []
        trade_offs: list[str] = []
        risk_score = 0

        # Check macro simulation for risks
        if context.simulation_result:
            deltas = context.simulation_result.get("metric_deltas", {})
            
            inflation_delta = deltas.get("inflation_pct", 0.0)
            if inflation_delta > 1.5:
                flagged_risks.append(f"High inflationary pressure (+{inflation_delta:.1f}%)")
                risk_score += 2
            elif inflation_delta > 0.5:
                flagged_risks.append("Moderate inflationary trend")
                risk_score += 1
                
            fiscal_stress_delta = deltas.get("fiscal_stress_index", 0.0)
            if fiscal_stress_delta > 5.0:
                flagged_risks.append(f"Significant worsening of fiscal position (+{fiscal_stress_delta:.1f} pts)")
                risk_score += 2
                
            unemployment_delta = deltas.get("unemployment_pct", 0.0)
            if unemployment_delta > 1.0:
                flagged_risks.append(f"Rising unemployment risk (+{unemployment_delta:.1f}%)")
                risk_score += 2
                
            # Trade-offs
            gdp_delta = deltas.get("gdp_growth_pct", 0.0)
            if gdp_delta > 0.5 and inflation_delta > 0.5:
                trade_offs.append("Growth is accelerating, but at the cost of higher inflation.")
            if gdp_delta > 0.5 and fiscal_stress_delta > 2.0:
                trade_offs.append("Growth is being driven by deficit spending, worsening fiscal stress.")
            if inflation_delta < -0.5 and unemployment_delta > 0.5:
                trade_offs.append("Inflation is contained, but at the cost of rising unemployment.")

        # Check micro/citizen data for personal risks
        if context.user_profile:
            # We assume CitizenAgent ran before this if we wanted full blended impact,
            # but we can do a lightweight structural check here anyway.
            income = float(context.user_profile.get("annual_income", 0))
            if income < 300000 and inflation_delta > 0.5:
                flagged_risks.append("High vulnerability to inflation due to low income bracket.")
                risk_score += 1

        if risk_score >= 4:
            risk_level = "critical"
        elif risk_score >= 2:
            risk_level = "high"
        elif risk_score == 1:
            risk_level = "moderate"
        else:
            risk_level = "low"
            
        if not flagged_risks:
            flagged_risks.append("No major acute risks identified in this scenario.")

        return {
            "risk_level": risk_level,
            "flagged_risks": flagged_risks,
            "trade_offs": trade_offs,
        }
