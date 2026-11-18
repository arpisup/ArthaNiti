from __future__ import annotations

import csv
import math
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

from ecosim.storage import (
    ensure_project_layout,
    latest_run_directory,
    remove_and_recreate_dir,
    utc_timestamp,
    write_csv,
    write_json,
    write_text,
)

WORLD_BANK_CODE_TO_METRIC = {
    "NY.GDP.MKTP.KD.ZG": "gdp_growth_pct",
    "FP.CPI.TOTL.ZG": "inflation_pct",
    "SL.UEM.TOTL.ZS": "unemployment_pct",
    "FR.INR.RINR": "real_interest_rate_pct",
    "PA.NUS.FCRF": "exchange_rate",
    "GC.DOD.TOTL.GD.ZS": "debt_to_gdp_pct",
    "GC.TAX.TOTL.GD.ZS": "tax_to_gdp_pct",
    "BX.KLT.DINV.WD.GD.ZS": "fdi_to_gdp_pct",
    "NE.TRD.GNFS.ZS": "trade_to_gdp_pct",
    "NV.AGR.TOTL.ZS": "agriculture_share_pct",
    "NV.IND.TOTL.ZS": "industry_share_pct",
    "NV.SRV.TOTL.ZS": "services_share_pct",
    "NY.GDP.MKTP.CD": "gdp_current_usd",
    "SP.POP.TOTL": "population_total",
    "GC.XPN.TOTL.GD.ZS": "govt_expenditure_to_gdp_pct",
    "NE.GDI.TOTL.ZS": "gross_capital_formation_to_gdp_pct",
    "SL.TLF.TOTL.IN": "labour_force_total",
    "NE.CON.PRVT.ZS": "household_consumption_to_gdp_pct",
    "NE.EXP.GNFS.ZS": "exports_to_gdp_pct",
    "NE.IMP.GNFS.ZS": "imports_to_gdp_pct",
    "SP.POP.DPND": "dependency_ratio_pct",
    "SI.POV.DDAY": "poverty_rate_pct",
    "SE.PRM.ENRR": "primary_school_enrollment_pct",
    "IT.NET.USER.ZS": "internet_users_pct",
    "EG.FEC.RNEW.ZS": "renewable_energy_share_pct",
    "NY.GDP.PCAP.KD": "gdp_per_capita_usd",
    "SL.TLF.CACT.ZS": "labor_force_participation_pct",
    "SP.RUR.TOTL.ZS": "rural_population_pct",
    "EN.ATM.CO2E.KT": "co2_emissions_kt",
}



def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _to_float(value: str | None) -> float | None:
    if value in (None, "", "None"):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _linear_slope(points: list[tuple[int, float]]) -> float:
    if len(points) < 2:
        return 0.0

    x_values = [point[0] for point in points]
    y_values = [point[1] for point in points]
    x_mean = mean(x_values)
    y_mean = mean(y_values)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in points)
    denominator = sum((x - x_mean) ** 2 for x in x_values)
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _load_records(path: Path) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    by_indicator: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(row)
            code = row["indicator_code"]
            bucket = by_indicator.setdefault(
                code,
                {
                    "indicator_code": code,
                    "indicator_name": row["indicator_name"],
                    "unit": row["unit"],
                    "rows": [],
                },
            )
            numeric_value = _to_float(row["value"])
            bucket["rows"].append(
                {
                    "year": int(row["year"]),
                    "value": numeric_value,
                    "country": row["country"],
                    "country_name": row["country_name"],
                    "unit": row["unit"],
                }
            )

    for bucket in by_indicator.values():
        bucket["rows"].sort(key=lambda item: item["year"])

    return by_indicator, rows


def _series_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    valid_points = [(row["year"], row["value"]) for row in rows if row["value"] is not None]
    if not valid_points:
        return {
            "series": rows,
            "coverage_count": 0,
            "latest_year": None,
            "latest_value": None,
            "five_year_average": None,
            "ten_year_slope": 0.0,
            "ten_year_volatility": 0.0,
        }

    last_five = valid_points[-5:]
    last_ten = valid_points[-10:]
    last_values = [value for _, value in last_ten]
    latest_year, latest_value = valid_points[-1]
    return {
        "series": rows,
        "coverage_count": len(valid_points),
        "latest_year": latest_year,
        "latest_value": latest_value,
        "five_year_average": mean([value for _, value in last_five]),
        "ten_year_slope": _linear_slope(last_ten),
        "ten_year_volatility": pstdev(last_values) if len(last_values) > 1 else 0.0,
    }


def _latest_value(indicators: dict[str, dict[str, Any]], code: str, default: float = 0.0) -> float:
    value = indicators.get(code, {}).get("latest_value")
    if value is None:
        return default
    return float(value)


def _latest_year(indicators: dict[str, dict[str, Any]], code: str) -> int | None:
    raw = indicators.get(code, {}).get("latest_year")
    return int(raw) if raw is not None else None


def _build_macro_baseline(indicators: dict[str, dict[str, Any]]) -> dict[str, float]:
    gdp_growth = _latest_value(indicators, "NY.GDP.MKTP.KD.ZG")
    inflation = _latest_value(indicators, "FP.CPI.TOTL.ZG")
    unemployment = _latest_value(indicators, "SL.UEM.TOTL.ZS")
    real_interest = _latest_value(indicators, "FR.INR.RINR")
    debt = _latest_value(indicators, "GC.DOD.TOTL.GD.ZS")
    tax = _latest_value(indicators, "GC.TAX.TOTL.GD.ZS")
    trade = _latest_value(indicators, "NE.TRD.GNFS.ZS")
    fdi = _latest_value(indicators, "BX.KLT.DINV.WD.GD.ZS")
    exchange_rate = _latest_value(indicators, "PA.NUS.FCRF")
    exchange_volatility = indicators.get("PA.NUS.FCRF", {}).get("ten_year_volatility") or 0.0

    fiscal_stress = clamp(36 + max(0.0, debt - 45) * 0.9 - tax * 0.7, 5, 95)
    investment_sentiment = clamp(46 + fdi * 5.0 + (gdp_growth - 5.0) * 3.8 - inflation * 1.7, 5, 95)
    household_pressure = clamp(34 + inflation * 3.2 + unemployment * 4.1 - gdp_growth * 1.6, 5, 95)
    exchange_stability = clamp(
        84 - inflation * 2.1 - exchange_volatility * 0.8 + max(real_interest, 0) * 1.0,
        5,
        95,
    )
    trade_momentum = clamp(22 + trade * 0.75 + fdi * 3.5 - exchange_volatility * 0.3, 5, 95)

    return {
        "gdp_growth_pct": gdp_growth,
        "inflation_pct": inflation,
        "unemployment_pct": unemployment,
        "real_interest_rate_pct": real_interest,
        "debt_to_gdp_pct": debt,
        "tax_to_gdp_pct": tax,
        "trade_to_gdp_pct": trade,
        "fdi_to_gdp_pct": fdi,
        "exchange_rate": exchange_rate,
        "fiscal_stress_index": fiscal_stress,
        "investment_sentiment_index": investment_sentiment,
        "household_pressure_index": household_pressure,
        "exchange_stability_index": exchange_stability,
        "trade_momentum_index": trade_momentum,
        "agriculture_share_pct": _latest_value(indicators, "NV.AGR.TOTL.ZS"),
        "industry_share_pct": _latest_value(indicators, "NV.IND.TOTL.ZS"),
        "services_share_pct": _latest_value(indicators, "NV.SRV.TOTL.ZS"),
        "gdp_current_usd": _latest_value(indicators, "NY.GDP.MKTP.CD"),
        "population_total": _latest_value(indicators, "SP.POP.TOTL"),
        "govt_expenditure_to_gdp_pct": _latest_value(indicators, "GC.XPN.TOTL.GD.ZS"),
        "gross_capital_formation_to_gdp_pct": _latest_value(indicators, "NE.GDI.TOTL.ZS"),
        "labour_force_total": _latest_value(indicators, "SL.TLF.TOTL.IN"),
        "household_consumption_to_gdp_pct": _latest_value(indicators, "NE.CON.PRVT.ZS"),
        "exports_to_gdp_pct": _latest_value(indicators, "NE.EXP.GNFS.ZS"),
        "imports_to_gdp_pct": _latest_value(indicators, "NE.IMP.GNFS.ZS"),
        "dependency_ratio_pct": _latest_value(indicators, "SP.POP.DPND"),
        "poverty_rate_pct": _latest_value(indicators, "SI.POV.DDAY"),
        "primary_school_enrollment_pct": _latest_value(indicators, "SE.PRM.ENRR"),
        "internet_users_pct": _latest_value(indicators, "IT.NET.USER.ZS"),
        "renewable_energy_share_pct": _latest_value(indicators, "EG.FEC.RNEW.ZS"),
        "gdp_per_capita_usd": _latest_value(indicators, "NY.GDP.PCAP.KD"),
        "labor_force_participation_pct": _latest_value(indicators, "SL.TLF.CACT.ZS"),
        "rural_population_pct": _latest_value(indicators, "SP.RUR.TOTL.ZS"),
        "co2_emissions_kt": _latest_value(indicators, "EN.ATM.CO2E.KT"),
    }


def _collect_manual_sources(base_dir: Path) -> list[dict[str, Any]]:
    manual_root = base_dir / "data/raw/manual"
    if not manual_root.exists():
        return []

    manifests: list[dict[str, Any]] = []
    for source_dir in sorted(path for path in manual_root.iterdir() if path.is_dir()):
        latest = latest_run_directory(source_dir)
        if not latest:
            continue
        manifest_path = latest / "manifest.json"
        if not manifest_path.exists():
            continue
        payload = __import__("json").loads(manifest_path.read_text(encoding="utf-8"))
        manifests.append(payload)
    return manifests


def _build_overview(snapshot: dict[str, Any]) -> str:
    baseline = snapshot["macro_baseline"]
    stale = snapshot["data_quality"]["stale_indicators"]
    manual_sources = snapshot["manual_sources"]

    lines = [
        "# Processed Data Overview",
        "",
        f"Processed run: `{snapshot['run_id']}`",
        f"Source World Bank run: `{snapshot['source_world_bank_run_id']}`",
        f"Baseline year: `{snapshot['baseline_year']}`",
        "",
        "## Core macro anchors",
        "",
        f"- GDP growth baseline: `{baseline['gdp_growth_pct']:.2f}%`",
        f"- Inflation baseline: `{baseline['inflation_pct']:.2f}%`",
        f"- Unemployment baseline: `{baseline['unemployment_pct']:.2f}%`",
        f"- Fiscal stress baseline: `{baseline['fiscal_stress_index']:.1f}`",
        f"- Investment sentiment baseline: `{baseline['investment_sentiment_index']:.1f}`",
        f"- Household pressure baseline: `{baseline['household_pressure_index']:.1f}`",
        "",
        "## Data quality",
        "",
    ]

    if stale:
        lines.extend([f"- Stale indicators detected: `{', '.join(stale)}`"])
    else:
        lines.append("- No stale indicators were detected in the current snapshot.")

    if manual_sources:
        lines.extend(["", "## Registered manual sources", ""])
        for source in manual_sources:
            lines.append(
                f"- `{source['source_id']}`: `{source['input_file_name']}` with SHA-256 `{source['sha256']}`"
            )
    else:
        lines.extend(["", "## Registered manual sources", "", "- None registered in the current workspace."])

    lines.extend(
        [
            "",
            "## Modeling note",
            "",
            "The scenario engine is anchored to these macro baselines, but policy-to-outcome elasticities are transparent heuristics rather than a validated causal macroeconomic model.",
        ]
    )
    return "\n".join(lines) + "\n"


def prepare_processed_data(base_dir: Path) -> dict[str, Any]:
    ensure_project_layout(base_dir)

    latest_world_bank = latest_run_directory(base_dir / "data/raw/world_bank")
    if not latest_world_bank:
        raise FileNotFoundError("No World Bank run found. Run collect-world-bank first.")

    records_path = latest_world_bank / "records.csv"
    if not records_path.exists():
        raise FileNotFoundError(f"World Bank records file missing: {records_path}")

    indicators, raw_rows = _load_records(records_path)
    indicator_catalog: dict[str, dict[str, Any]] = {}
    for code, payload in indicators.items():
        stats = _series_stats(payload["rows"])
        indicator_catalog[code] = {
            "indicator_code": code,
            "indicator_name": payload["indicator_name"],
            "unit": payload["unit"],
            "metric_id": WORLD_BANK_CODE_TO_METRIC.get(code),
            **stats,
        }

    available_years = [stats["latest_year"] for stats in indicator_catalog.values() if stats["latest_year"] is not None]
    baseline_year = max(available_years) if available_years else None
    stale_indicators = sorted(
        code
        for code, stats in indicator_catalog.items()
        if baseline_year is not None and stats["latest_year"] is not None and stats["latest_year"] < baseline_year - 1
    )

    run_id = utc_timestamp()
    run_dir = base_dir / "data/processed" / run_id
    latest_dir = base_dir / "data/processed/latest"
    run_dir.mkdir(parents=True, exist_ok=True)
    remove_and_recreate_dir(latest_dir)

    manual_sources = _collect_manual_sources(base_dir)
    macro_baseline = _build_macro_baseline(indicator_catalog)

    pivot_rows: list[dict[str, Any]] = []
    years = sorted({int(row["year"]) for row in raw_rows})
    codes = sorted(indicator_catalog)
    row_lookup: dict[tuple[int, str], str] = {
        (int(row["year"]), row["indicator_code"]): row["value"] for row in raw_rows
    }
    for year in years:
        pivot_row: dict[str, Any] = {"year": year}
        for code in codes:
            pivot_row[code] = row_lookup.get((year, code), "")
        pivot_rows.append(pivot_row)

    write_csv(run_dir / "macro_history.csv", ["year", *codes], pivot_rows)
    write_csv(latest_dir / "macro_history.csv", ["year", *codes], pivot_rows)

    snapshot = {
        "run_id": run_id,
        "source_world_bank_run_id": latest_world_bank.name,
        "baseline_year": baseline_year,
        "indicator_catalog": indicator_catalog,
        "macro_baseline": macro_baseline,
        "manual_sources": manual_sources,
        "data_quality": {
            "stale_indicators": stale_indicators,
            "indicator_count": len(indicator_catalog),
        },
    }
    overview = _build_overview(snapshot)
    write_json(run_dir / "snapshot.json", snapshot)
    write_json(latest_dir / "snapshot.json", snapshot)
    write_text(run_dir / "overview.md", overview)
    write_text(latest_dir / "overview.md", overview)

    manifest = {
        "run_id": run_id,
        "processed_snapshot": str(run_dir / "snapshot.json"),
        "latest_snapshot": str(latest_dir / "snapshot.json"),
        "macro_history_csv": str(run_dir / "macro_history.csv"),
        "overview_path": str(run_dir / "overview.md"),
        "baseline_year": baseline_year,
        "source_world_bank_run_id": latest_world_bank.name,
        "stale_indicator_count": len(stale_indicators),
    }
    write_json(run_dir / "manifest.json", manifest)
    write_json(latest_dir / "manifest.json", manifest)
    return manifest


def load_processed_snapshot(base_dir: Path) -> dict[str, Any]:
    path = base_dir / "data/processed/latest/snapshot.json"
    if not path.exists():
        raise FileNotFoundError("Processed snapshot not found. Run prepare-data first.")
    return __import__("json").loads(path.read_text(encoding="utf-8"))
