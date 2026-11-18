from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ecosim.storage import ensure_phase1_layout, utc_timestamp, write_csv, write_json

WORLD_BANK_API_BASE = "https://api.worldbank.org/v2"
WORLD_BANK_FIELDNAMES = (
    "country",
    "country_name",
    "indicator_code",
    "indicator_name",
    "year",
    "value",
    "unit",
    "obs_status",
    "decimal",
)
WORLD_BANK_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/135.0 Safari/537.36 EcoSim/0.1"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "close",
}


@dataclass(frozen=True)
class IndicatorConfig:
    code: str
    name: str


@dataclass(frozen=True)
class WorldBankConfig:
    country: str
    start_year: int
    end_year: int
    indicators: list[IndicatorConfig]
    raw: dict[str, Any]


def load_world_bank_config(path: Path) -> WorldBankConfig:
    payload = json.loads(path.read_text(encoding="utf-8"))
    country = str(payload["country"]).upper()
    start_year = int(payload["start_year"])
    end_year = int(payload["end_year"])
    indicators = [
        IndicatorConfig(code=str(item["code"]), name=str(item["name"]))
        for item in payload["indicators"]
    ]

    if start_year > end_year:
        raise ValueError("start_year must be <= end_year")
    if not indicators:
        raise ValueError("At least one indicator is required")

    return WorldBankConfig(
        country=country,
        start_year=start_year,
        end_year=end_year,
        indicators=indicators,
        raw=payload,
    )


def _build_world_bank_url(
    country: str,
    indicator_code: str,
    start_year: int,
    end_year: int,
    page: int,
    per_page: int,
) -> str:
    params = {
        "format": "json",
        "source": 2,
        "per_page": per_page,
        "page": page,
        "date": f"{start_year}:{end_year}",
    }
    return f"{WORLD_BANK_API_BASE}/country/{country}/indicator/{indicator_code}?{urlencode(params)}"


def _extract_world_bank_error(payload: Any) -> str | None:
    if not isinstance(payload, list) or not payload:
        return None

    first_item = payload[0]
    messages = first_item.get("message") if isinstance(first_item, dict) else None
    if not isinstance(messages, list):
        return None

    parts: list[str] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        message_id = message.get("id")
        value = message.get("value")
        if message_id and value:
            parts.append(f"{message_id}: {value}")
        elif value:
            parts.append(str(value))

    return "; ".join(parts) if parts else "Unknown World Bank API error"


def _parse_world_bank_payload(payload: Any, indicator_code: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    error_message = _extract_world_bank_error(payload)
    if error_message:
        raise ValueError(f"API error for {indicator_code}: {error_message}")

    if not isinstance(payload, list) or len(payload) != 2:
        raise ValueError(f"Unexpected response shape for {indicator_code}")

    metadata, rows = payload
    if not isinstance(metadata, dict):
        raise ValueError(f"Invalid metadata block for {indicator_code}")
    if rows is None:
        rows = []
    if not isinstance(rows, list):
        raise ValueError(f"Invalid row block for {indicator_code}")

    return metadata, rows


def _fetch_world_bank_page(
    url: str,
    indicator_code: str,
    retries: int,
    timeout_seconds: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            request = Request(url, headers=WORLD_BANK_HEADERS)
            with urlopen(request, timeout=timeout_seconds) as response:
                body = response.read().decode("utf-8")
            payload = json.loads(body)
            return _parse_world_bank_payload(payload, indicator_code)
        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt == retries:
                break
            wait_seconds = min(10.0, 1.5 * (2 ** (attempt - 1)) + random.uniform(0.15, 0.85))
            time.sleep(wait_seconds)

    raise RuntimeError(f"World Bank request failed for {indicator_code}: {last_error}") from last_error


def fetch_world_bank_payload(
    country: str,
    indicator_code: str,
    start_year: int,
    end_year: int,
    retries: int = 4,
    timeout_seconds: int = 45,
    per_page: int = 1000,
) -> dict[str, Any]:
    all_rows: list[dict[str, Any]] = []
    metadata_snapshot: dict[str, Any] | None = None
    page = 1
    total_pages = 1

    while page <= total_pages:
        url = _build_world_bank_url(
            country=country,
            indicator_code=indicator_code,
            start_year=start_year,
            end_year=end_year,
            page=page,
            per_page=per_page,
        )
        metadata, rows = _fetch_world_bank_page(
            url=url,
            indicator_code=indicator_code,
            retries=retries,
            timeout_seconds=timeout_seconds,
        )
        if metadata_snapshot is None:
            metadata_snapshot = metadata
            total_pages = int(metadata.get("pages") or 1)

        all_rows.extend(rows)
        page += 1

    request_url = _build_world_bank_url(
        country=country,
        indicator_code=indicator_code,
        start_year=start_year,
        end_year=end_year,
        page=1,
        per_page=per_page,
    )
    return {
        "request_url": request_url,
        "metadata": metadata_snapshot or {},
        "rows": all_rows,
    }


def normalize_indicator_rows(
    country: str,
    indicator: IndicatorConfig,
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        raw_year = row.get("date")
        try:
            year = int(raw_year)
        except (TypeError, ValueError):
            continue

        country_info = row.get("country") or {}
        normalized.append(
            {
                "country": country,
                "country_name": country_info.get("value") or row.get("countryiso3code") or country,
                "indicator_code": indicator.code,
                "indicator_name": indicator.name,
                "year": year,
                "value": row.get("value"),
                "unit": row.get("unit"),
                "obs_status": row.get("obs_status"),
                "decimal": row.get("decimal"),
            }
        )

    normalized.sort(key=lambda item: (item["indicator_code"], item["year"]))
    return normalized


def _load_cached_indicator_payload(
    base_dir: Path,
    indicator_code: str,
    current_run_dir: Path,
) -> tuple[dict[str, Any], str] | None:
    world_bank_root = base_dir / "data/raw/world_bank"
    if not world_bank_root.exists():
        return None

    run_directories = sorted(
        (path for path in world_bank_root.iterdir() if path.is_dir() and path != current_run_dir),
        reverse=True,
    )
    for run_dir in run_directories:
        candidate = run_dir / f"{indicator_code}.json"
        if not candidate.exists():
            continue
        payload = json.loads(candidate.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
            return payload, run_dir.name
    return None


def collect_world_bank(base_dir: Path, config_path: Path) -> dict[str, Any]:
    ensure_phase1_layout(base_dir)
    config = load_world_bank_config(config_path)
    run_id = utc_timestamp()
    run_dir = base_dir / "data/raw/world_bank" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    write_json(run_dir / "config.snapshot.json", config.raw)

    all_rows: list[dict[str, Any]] = []
    indicators_summary: list[dict[str, Any]] = []
    warnings: list[str] = []

    for indicator in config.indicators:
        fetch_status = "live"
        cached_from = None
        warning = None
        try:
            payload = fetch_world_bank_payload(
                country=config.country,
                indicator_code=indicator.code,
                start_year=config.start_year,
                end_year=config.end_year,
            )
        except RuntimeError as exc:
            cached_payload = _load_cached_indicator_payload(base_dir, indicator.code, run_dir)
            if not cached_payload:
                raise
            payload, cached_from = cached_payload
            fetch_status = "cached"
            warning = str(exc)
            warnings.append(
                f"{indicator.code} reused cached payload from {cached_from} after live fetch failed: {exc}"
            )

        write_json(
            run_dir / f"{indicator.code}.json",
            {
                **payload,
                "fetch_status": fetch_status,
                "cached_from": cached_from,
                "warning": warning,
            },
        )

        normalized_rows = normalize_indicator_rows(config.country, indicator, payload["rows"])
        all_rows.extend(normalized_rows)
        indicators_summary.append(
            {
                "code": indicator.code,
                "name": indicator.name,
                "records": len(normalized_rows),
                "fetch_status": fetch_status,
                "cached_from": cached_from,
            }
        )

    write_csv(run_dir / "records.csv", WORLD_BANK_FIELDNAMES, all_rows)

    manifest = {
        "run_id": run_id,
        "source": "world_bank",
        "country": config.country,
        "start_year": config.start_year,
        "end_year": config.end_year,
        "indicator_count": len(config.indicators),
        "record_count": len(all_rows),
        "indicators": indicators_summary,
        "warnings": warnings,
        "artifacts": {
            "run_dir": str(run_dir),
            "normalized_csv": str(run_dir / "records.csv"),
        },
    }
    write_json(run_dir / "manifest.json", manifest)
    write_json(base_dir / "data/metadata/runs" / f"{run_id}_world_bank.json", manifest)
    return manifest
