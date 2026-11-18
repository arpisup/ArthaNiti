from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ecosim.storage import ensure_project_layout, remove_and_recreate_dir, utc_timestamp, write_csv, write_json

GOAL_COLUMNS = [f"sdg_{goal}" for goal in range(1, 17)]

NAME_CANONICAL_MAP = {
    "A and N Islands": "Andaman and Nicobar Islands",
    "Andaman and Nicobar IslandsJharkhand": "Jharkhand",
    "D and N Haveli": "Dadra and Nagar Haveli",
    "Daman & Diu": "Daman and Diu",
    "Jammu & Kashmir": "Jammu and Kashmir",
}

UNION_TERRITORIES = {
    "Andaman and Nicobar Islands",
    "Chandigarh",
    "Dadra and Nagar Haveli",
    "Daman and Diu",
    "Dadra and Nagar Haveli and Daman and Diu",
    "Delhi",
    "Jammu and Kashmir",
    "Lakshadweep",
    "Ladakh",
    "Puducherry",
}


@dataclass(frozen=True)
class SDGReportProfile:
    key: str
    report_cycle: str
    table_page: int
    mode: str
    filename_patterns: tuple[str, ...]
    ordered_goals: tuple[int, ...]


PROFILES = (
    SDGReportProfile(
        key="sdg_2019_20",
        report_cycle="2019-20",
        table_page=18,
        mode="stream_2019_20",
        filename_patterns=("SDG-India-Index-2021.pdf",),
        ordered_goals=(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 15, 16),
    ),
    SDGReportProfile(
        key="sdg_2020_21",
        report_cycle="2020-21",
        table_page=46,
        mode="stream_2020_21",
        filename_patterns=("SDG_India_Index_2020.pdf",),
        ordered_goals=(7, 6, 12, 16, 11, 3, 10, 1, 15, 8, 4, 2, 13, 5, 9),
    ),
    SDGReportProfile(
        key="sdg_2023_24",
        report_cycle="2023-24",
        table_page=87,
        mode="stream_2023_24",
        filename_patterns=("SDA_INDIA_INDEX_2023.pdf",),
        ordered_goals=(7, 6, 16, 15, 3, 8, 10, 11, 12, 1, 2, 13, 4, 9, 5),
    ),
)


def _import_tabula() -> Any:
    try:
        import tabula  # type: ignore
    except ImportError as exc:  # pragma: no cover - environment-specific
        raise RuntimeError(
            "SDG PDF extraction requires tabula-py. Install the optional 'sdg' dependency "
            "or use the repo venv where tabula-py is available."
        ) from exc
    return tabula


def _detect_profile(pdf_path: Path) -> SDGReportProfile:
    name = pdf_path.name
    for profile in PROFILES:
        if any(pattern in name for pattern in profile.filename_patterns):
            return profile
    raise ValueError(f"No SDG extraction profile matches {name}")


def _clean_name(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    text = re.sub(r"\s+", " ", text)
    return NAME_CANONICAL_MAP.get(text, text)


def _parse_int(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan" or text.lower() == "null":
        return None
    match = re.search(r"-?\d+", text)
    return int(match.group(0)) if match else None


def _row_type(name: str) -> str:
    if name == "India":
        return "india"
    if name == "Target":
        return "target"
    if name in UNION_TERRITORIES:
        return "union_territory"
    return "state"


def _base_record(profile: SDGReportProfile, pdf_path: Path, name: str) -> dict[str, Any]:
    return {
        "report_profile": profile.key,
        "report_cycle": profile.report_cycle,
        "source_file": pdf_path.name,
        "name": name,
        "row_type": _row_type(name),
        **{column: None for column in GOAL_COLUMNS},
        "composite_score": None,
    }


def _finalize_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for record in records:
        if not record["name"]:
            continue
        if record["composite_score"] is None and record["row_type"] not in {"india", "target"}:
            continue
        cleaned.append(record)
    return cleaned


def _clean_2019_20_table(table: Any, profile: SDGReportProfile, pdf_path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for _, row in table.iterrows():
        name = _clean_name(row.get("Unnamed: 1"))
        if not name or name == "States/UTs":
            continue

        composite = _parse_int(row.get("Composite"))
        split_scores = re.findall(r"-?\d+|Null", str(row.get("Unnamed: 9") or ""))
        if len(split_scores) < 2:
            continue

        record = _base_record(profile, pdf_path, name)
        record.update(
            {
                "sdg_1": _parse_int(row.get("Unnamed: 2")),
                "sdg_2": _parse_int(row.get("Unnamed: 3")),
                "sdg_3": _parse_int(row.get("Unnamed: 4")),
                "sdg_4": _parse_int(row.get("Unnamed: 5")),
                "sdg_5": _parse_int(row.get("Unnamed: 6")),
                "sdg_6": _parse_int(row.get("Unnamed: 7")),
                "sdg_7": _parse_int(row.get("Unnamed: 8")),
                "sdg_8": _parse_int(split_scores[0]),
                "sdg_9": _parse_int(split_scores[1]),
                "sdg_10": _parse_int(row.get("Unnamed: 11")),
                "sdg_11": _parse_int(row.get("Unnamed: 12")),
                "sdg_12": _parse_int(row.get("Unnamed: 13")),
                "sdg_13": _parse_int(row.get("Unnamed: 14")),
                "sdg_15": _parse_int(row.get("Unnamed: 15")),
                "sdg_16": _parse_int(row.get("Unnamed: 16")),
                "composite_score": composite,
            }
        )
        records.append(record)

    return _finalize_records(records)


def _clean_2020_21_table(table: Any, profile: SDGReportProfile, pdf_path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    rows = table.to_dict(orient="records")
    index = 0
    while index < len(rows):
        row = rows[index]
        name = _clean_name(row.get("States"))

        if not name:
            index += 1
            continue

        if name == "Dadra and Nagar Haveli &":
            score_row = rows[index + 1]
            record = _base_record(profile, pdf_path, "Dadra and Nagar Haveli and Daman and Diu")
            for goal in profile.ordered_goals:
                record[f"sdg_{goal}"] = _parse_int(score_row.get(f"SDG{goal}"))
            record["composite_score"] = _parse_int(score_row.get("Composite SDG"))
            records.append(record)
            index += 3
            continue

        record = _base_record(profile, pdf_path, name)
        for goal in profile.ordered_goals:
            record[f"sdg_{goal}"] = _parse_int(row.get(f"SDG{goal}"))
        record["composite_score"] = _parse_int(row.get("Composite SDG"))
        records.append(record)
        index += 1

    return _finalize_records(records)


def _clean_2023_24_table(table: Any, profile: SDGReportProfile, pdf_path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    rows = table.to_dict(orient="records")
    index = 0
    while index < len(rows):
        row = rows[index]
        name = _clean_name(row.get("Unnamed: 0"))
        if not name or name == "STATES":
            index += 1
            continue

        if name == "Dadra and Nagar Haveli and":
            name = "Dadra and Nagar Haveli and Daman and Diu"
            index += 2
            source_row = row
        else:
            source_row = row
            index += 1

        record = _base_record(profile, pdf_path, name)
        for goal_offset, goal in enumerate(profile.ordered_goals, start=1):
            record[f"sdg_{goal}"] = _parse_int(source_row.get(f"Unnamed: {goal_offset}"))
        record["composite_score"] = _parse_int(source_row.get("Composite"))
        records.append(record)

    return _finalize_records(records)


def extract_sdg_report(pdf_path: Path) -> dict[str, Any]:
    tabula = _import_tabula()
    profile = _detect_profile(pdf_path)
    table = tabula.read_pdf(
        str(pdf_path),
        pages=profile.table_page,
        multiple_tables=True,
        stream=True,
    )[0]

    if profile.mode == "stream_2019_20":
        records = _clean_2019_20_table(table, profile, pdf_path)
    elif profile.mode == "stream_2020_21":
        records = _clean_2020_21_table(table, profile, pdf_path)
    elif profile.mode == "stream_2023_24":
        records = _clean_2023_24_table(table, profile, pdf_path)
    else:  # pragma: no cover - defensive
        raise ValueError(f"Unknown SDG extraction mode: {profile.mode}")

    return {
        "profile": profile,
        "records": records,
    }


def _wide_fieldnames() -> list[str]:
    return [
        "report_profile",
        "report_cycle",
        "source_file",
        "name",
        "row_type",
        *GOAL_COLUMNS,
        "composite_score",
    ]


def _long_rows(wide_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for wide_row in wide_rows:
        for goal in range(1, 17):
            rows.append(
                {
                    "report_profile": wide_row["report_profile"],
                    "report_cycle": wide_row["report_cycle"],
                    "source_file": wide_row["source_file"],
                    "name": wide_row["name"],
                    "row_type": wide_row["row_type"],
                    "goal": goal,
                    "score": wide_row[f"sdg_{goal}"],
                    "composite_score": wide_row["composite_score"],
                }
            )
    return rows


def extract_sdg_directory(base_dir: Path, input_dir: Path) -> dict[str, Any]:
    ensure_project_layout(base_dir)
    source_dir = input_dir.resolve()
    if not source_dir.exists():
        raise FileNotFoundError(f"SDG input directory not found: {source_dir}")

    run_id = utc_timestamp()
    run_dir = base_dir / "data/processed/sdg" / run_id
    latest_dir = base_dir / "data/processed/sdg/latest"
    run_dir.mkdir(parents=True, exist_ok=True)
    remove_and_recreate_dir(latest_dir)

    pdf_files = sorted(path for path in source_dir.iterdir() if path.is_file() and path.suffix.lower() == ".pdf")
    if not pdf_files:
        raise FileNotFoundError(f"No PDF files found in {source_dir}")

    combined_rows: list[dict[str, Any]] = []
    report_outputs: list[dict[str, Any]] = []

    for pdf_path in pdf_files:
        extracted = extract_sdg_report(pdf_path)
        profile: SDGReportProfile = extracted["profile"]
        records: list[dict[str, Any]] = extracted["records"]
        combined_rows.extend(records)

        file_slug = f"{profile.report_cycle.replace('-', '_')}_goal_scores.csv"
        write_csv(run_dir / file_slug, _wide_fieldnames(), records)
        write_csv(latest_dir / file_slug, _wide_fieldnames(), records)
        report_outputs.append(
            {
                "source_file": pdf_path.name,
                "report_cycle": profile.report_cycle,
                "profile": profile.key,
                "row_count": len(records),
                "output_csv": str(run_dir / file_slug),
            }
        )

    wide_rows = sorted(combined_rows, key=lambda item: (item["report_cycle"], item["row_type"], item["name"]))
    long_rows = _long_rows(wide_rows)

    write_csv(run_dir / "combined_goal_scores_wide.csv", _wide_fieldnames(), wide_rows)
    write_csv(latest_dir / "combined_goal_scores_wide.csv", _wide_fieldnames(), wide_rows)
    write_csv(
        run_dir / "combined_goal_scores_long.csv",
        [
            "report_profile",
            "report_cycle",
            "source_file",
            "name",
            "row_type",
            "goal",
            "score",
            "composite_score",
        ],
        long_rows,
    )
    write_csv(
        latest_dir / "combined_goal_scores_long.csv",
        [
            "report_profile",
            "report_cycle",
            "source_file",
            "name",
            "row_type",
            "goal",
            "score",
            "composite_score",
        ],
        long_rows,
    )

    manifest = {
        "run_id": run_id,
        "source_dir": str(source_dir),
        "report_count": len(report_outputs),
        "reports": report_outputs,
        "wide_output": str(run_dir / "combined_goal_scores_wide.csv"),
        "long_output": str(run_dir / "combined_goal_scores_long.csv"),
        "latest_dir": str(latest_dir),
    }
    write_json(run_dir / "manifest.json", manifest)
    write_json(latest_dir / "manifest.json", manifest)
    return manifest
