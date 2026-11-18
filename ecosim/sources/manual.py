from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ecosim.storage import copy_file, ensure_phase1_layout, sha256_file, utc_timestamp, write_json


@dataclass(frozen=True)
class ManualSource:
    id: str
    name: str
    automation: str
    category: str
    preferred_formats: tuple[str, ...]
    notes: str


def load_manual_registry(path: Path) -> dict[str, ManualSource]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    sources = payload.get("sources") or []
    registry = {
        entry["id"]: ManualSource(
            id=str(entry["id"]),
            name=str(entry["name"]),
            automation=str(entry["automation"]),
            category=str(entry["category"]),
            preferred_formats=tuple(entry.get("preferred_formats") or ()),
            notes=str(entry.get("notes") or ""),
        )
        for entry in sources
    }
    if not registry:
        raise ValueError("Manual source registry is empty")
    return registry


def register_manual_file(
    base_dir: Path,
    registry_path: Path,
    source_id: str,
    file_path: Path,
) -> dict[str, Any]:
    ensure_phase1_layout(base_dir)
    registry = load_manual_registry(registry_path)
    if source_id not in registry:
        raise KeyError(f"Unknown source_id '{source_id}'")

    source = registry[source_id]
    input_file = file_path.resolve()
    if not input_file.exists():
        raise FileNotFoundError(f"Input file does not exist: {input_file}")

    extension = input_file.suffix.lower()
    run_id = utc_timestamp()
    run_dir = base_dir / "data/raw/manual" / source_id / run_id
    copied_file = run_dir / "source" / input_file.name
    copy_file(input_file, copied_file)

    manifest = {
        "run_id": run_id,
        "source_id": source.id,
        "source_name": source.name,
        "automation": source.automation,
        "category": source.category,
        "preferred_formats": list(source.preferred_formats),
        "format_matches_preference": extension in source.preferred_formats,
        "notes": source.notes,
        "input_file_name": input_file.name,
        "copied_file": str(copied_file),
        "size_bytes": copied_file.stat().st_size,
        "sha256": sha256_file(copied_file),
    }
    write_json(run_dir / "manifest.json", manifest)
    write_json(base_dir / "data/metadata/runs" / f"{run_id}_manual_{source.id}.json", manifest)
    return manifest
