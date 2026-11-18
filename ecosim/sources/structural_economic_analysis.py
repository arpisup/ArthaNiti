from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


REQUIRED_COLUMNS = {"Name", "Acronym", "Description", "Publisher", "Language Supported", "URL", "Data Notes"}


def _clean_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def load_structural_economic_catalog(path: Path) -> list[dict[str, str]]:
    """Load the Kaggle structural economic analysis catalog into a normalized row list.

    The source file is a catalog of databases and metadata rather than a time-series
    table, so the loader normalizes rows into a flat mapping that can be stored and
    searched by the project without changing the rest of the simulation pipeline.
    """
    if not path.exists():
        raise FileNotFoundError(f"Catalog file does not exist: {path}")

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"Catalog file is empty or missing a header row: {path}")

        missing = REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing:
            raise ValueError(f"Catalog is missing required columns: {sorted(missing)}")

        rows: list[dict[str, str]] = []
        for row in reader:
            normalized = {
                "name": _clean_value(row.get("Name")),
                "acronym": _clean_value(row.get("Acronym")),
                "description": _clean_value(row.get("Description")),
                "publisher": _clean_value(row.get("Publisher")),
                "language_supported": _clean_value(row.get("Language Supported")),
                "url": _clean_value(row.get("URL")),
                "data_notes": _clean_value(row.get("Data Notes")),
            }
            if normalized["name"]:
                rows.append(normalized)

    return rows


def select_relevant_structural_sources(rows: list[dict[str, str]], keywords: list[str]) -> list[dict[str, str]]:
    keywords = [keyword.lower() for keyword in keywords]

    def matches(row: dict[str, str]) -> bool:
        haystack = "\n".join(
            [
                row.get("name", ""),
                row.get("description", ""),
                row.get("publisher", ""),
                row.get("data_notes", ""),
            ]
        ).lower()
        return any(keyword in haystack for keyword in keywords)

    return [row for row in rows if matches(row)]
