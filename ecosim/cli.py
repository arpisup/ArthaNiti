from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ecosim.documents import extract_document
from ecosim.knowledge import build_knowledge_index
from ecosim.processing import prepare_processed_data
from ecosim.server import serve
from ecosim.sources.manual import load_manual_registry, register_manual_file
from ecosim.sources.sdg import extract_sdg_directory
from ecosim.sources.world_bank import collect_world_bank
from ecosim.storage import ensure_project_layout


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ecosim",
        description="Eco Sim data, simulation, and local app commands.",
    )
    parser.add_argument(
        "--base-dir",
        default=".",
        help="Repo root for data and config output. Defaults to the current directory.",
    )

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("bootstrap", help="Create the project directory layout.")

    collect_world_bank_parser = subparsers.add_parser(
        "collect-world-bank",
        help="Fetch indicator data from the World Bank API.",
    )
    collect_world_bank_parser.add_argument(
        "--config",
        required=True,
        help="Path to a World Bank collection config JSON file.",
    )

    list_manual_sources_parser = subparsers.add_parser(
        "list-manual-sources",
        help="List registered manual intake sources.",
    )
    list_manual_sources_parser.add_argument(
        "--registry",
        required=True,
        help="Path to the manual source registry JSON file.",
    )

    register_manual_parser = subparsers.add_parser(
        "register-manual",
        help="Copy a manually sourced file into the managed raw-data store.",
    )
    register_manual_parser.add_argument(
        "--registry",
        required=True,
        help="Path to the manual source registry JSON file.",
    )
    register_manual_parser.add_argument(
        "--source-id",
        required=True,
        help="Source ID from the manual registry.",
    )
    register_manual_parser.add_argument(
        "--file",
        required=True,
        help="Absolute or relative path to the file to ingest.",
    )

    extract_document_parser = subparsers.add_parser(
        "extract-document",
        help="Copy a PDF and extract its text for later indexing.",
    )
    extract_document_parser.add_argument(
        "--document-id",
        required=True,
        help="Stable identifier for the document collection run.",
    )
    extract_document_parser.add_argument(
        "--file",
        required=True,
        help="Absolute or relative path to the PDF.",
    )

    subparsers.add_parser(
        "prepare-data",
        help="Build the processed data snapshot from the latest raw inputs.",
    )

    subparsers.add_parser(
        "build-knowledge",
        help="Build the retrieval index from repo docs and extracted documents.",
    )

    extract_sdg_parser = subparsers.add_parser(
        "extract-sdg",
        help="Convert supported SDG India report PDFs into cleaned CSVs.",
    )
    extract_sdg_parser.add_argument(
        "--input-dir",
        required=True,
        help="Directory containing supported SDG report PDFs.",
    )

    serve_parser = subparsers.add_parser(
        "serve",
        help="Run the local Eco Sim HTTP server.",
    )
    serve_parser.add_argument("--host", default="127.0.0.1", help="Bind host.")
    serve_parser.add_argument("--port", type=int, default=8000, help="Bind port.")
    serve_parser.add_argument(
        "--no-auto-build",
        action="store_true",
        help="Do not auto-build processed data or knowledge artifacts when missing.",
    )

    return parser


def _print_json(payload: object) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def run(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    base_dir = Path(args.base_dir).resolve()

    try:
        if args.command == "bootstrap":
            ensure_project_layout(base_dir)
            _print_json({"status": "ok", "base_dir": str(base_dir)})
            return 0

        if args.command == "collect-world-bank":
            manifest = collect_world_bank(base_dir=base_dir, config_path=Path(args.config).resolve())
            _print_json(manifest)
            return 0

        if args.command == "list-manual-sources":
            registry = load_manual_registry(Path(args.registry).resolve())
            payload = {
                "source_count": len(registry),
                "sources": [
                    {
                        "id": source.id,
                        "name": source.name,
                        "category": source.category,
                        "automation": source.automation,
                        "preferred_formats": list(source.preferred_formats),
                        "notes": source.notes,
                    }
                    for source in registry.values()
                ],
            }
            _print_json(payload)
            return 0

        if args.command == "register-manual":
            manifest = register_manual_file(
                base_dir=base_dir,
                registry_path=Path(args.registry).resolve(),
                source_id=args.source_id,
                file_path=Path(args.file),
            )
            _print_json(manifest)
            return 0

        if args.command == "extract-document":
            manifest = extract_document(
                base_dir=base_dir,
                document_id=args.document_id,
                file_path=Path(args.file),
            )
            _print_json(manifest)
            return 0

        if args.command == "prepare-data":
            manifest = prepare_processed_data(base_dir)
            _print_json(manifest)
            return 0

        if args.command == "build-knowledge":
            manifest = build_knowledge_index(base_dir)
            _print_json(manifest)
            return 0

        if args.command == "extract-sdg":
            manifest = extract_sdg_directory(
                base_dir=base_dir,
                input_dir=Path(args.input_dir),
            )
            _print_json(manifest)
            return 0

        if args.command == "serve":
            serve(
                base_dir=base_dir,
                host=args.host,
                port=args.port,
                auto_build=not args.no_auto_build,
            )
            return 0
    except Exception as exc:  # pragma: no cover - CLI error boundary
        print(f"error: {exc}", file=sys.stderr)
        return 1

    parser.print_help()
    return 1
