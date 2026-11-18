from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from ecosim.storage import copy_file, ensure_phase1_layout, sha256_file, utc_timestamp, write_json, write_text


def _extract_with_pymupdf(path: Path) -> tuple[str, list[dict[str, Any]]]:
    import fitz  # type: ignore

    pages: list[dict[str, Any]] = []
    with fitz.open(path) as document:
        for index, page in enumerate(document, start=1):
            text = page.get_text("text")
            pages.append(
                {
                    "page_number": index,
                    "text": text,
                    "char_count": len(text),
                }
            )
    return "PyMuPDF", pages


def _extract_with_pypdf(path: Path) -> tuple[str, list[dict[str, Any]]]:
    from pypdf import PdfReader  # type: ignore

    reader = PdfReader(str(path))
    pages: list[dict[str, Any]] = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append(
            {
                "page_number": index,
                "text": text,
                "char_count": len(text),
            }
        )
    return "pypdf", pages


def _extract_with_pdftotext(path: Path) -> tuple[str, list[dict[str, Any]]]:
    pdftotext_path = shutil.which("pdftotext")
    if not pdftotext_path:
        raise ImportError("pdftotext is not installed")

    pdfinfo_path = shutil.which("pdfinfo")
    if not pdfinfo_path:
        raise ImportError("pdfinfo is not installed")

    info_result = subprocess.run(
        [pdfinfo_path, str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    page_count = 0
    for line in info_result.stdout.splitlines():
        if line.startswith("Pages:"):
            page_count = int(line.split(":", maxsplit=1)[1].strip())
            break
    if page_count <= 0:
        raise RuntimeError(f"Could not determine page count for {path}")

    pages: list[dict[str, Any]] = []
    for page_number in range(1, page_count + 1):
        text_result = subprocess.run(
            [pdftotext_path, "-f", str(page_number), "-l", str(page_number), str(path), "-"],
            check=True,
            capture_output=True,
            text=True,
        )
        text = text_result.stdout
        pages.append(
            {
                "page_number": page_number,
                "text": text,
                "char_count": len(text),
            }
        )
    return "pdftotext", pages


def extract_pdf_pages(path: Path) -> tuple[str, list[dict[str, Any]]]:
    extractors = (_extract_with_pymupdf, _extract_with_pypdf, _extract_with_pdftotext)
    failures: list[str] = []

    for extractor in extractors:
        try:
            return extractor(path)
        except (ImportError, subprocess.CalledProcessError, RuntimeError) as exc:
            failures.append(str(exc))

    raise RuntimeError(
        "PDF extraction requires PyMuPDF, pypdf, or system tools pdftotext/pdfinfo. "
        f"Available backends failed: {json.dumps(failures)}"
    )


def extract_document(base_dir: Path, document_id: str, file_path: Path) -> dict[str, Any]:
    ensure_phase1_layout(base_dir)
    input_file = file_path.resolve()
    if not input_file.exists():
        raise FileNotFoundError(f"Input file does not exist: {input_file}")
    if input_file.suffix.lower() != ".pdf":
        raise ValueError("Only PDF documents are supported by extract-document")

    backend, pages = extract_pdf_pages(input_file)
    run_id = utc_timestamp()
    run_dir = base_dir / "data/raw/documents" / document_id / run_id
    copied_file = run_dir / "source" / input_file.name
    copy_file(input_file, copied_file)

    full_text = "\n\n".join(page["text"] for page in pages if page["text"].strip())
    write_json(run_dir / "pages.json", pages)
    write_text(run_dir / "full_text.txt", full_text)

    manifest = {
        "run_id": run_id,
        "document_id": document_id,
        "input_file_name": input_file.name,
        "copied_file": str(copied_file),
        "size_bytes": copied_file.stat().st_size,
        "sha256": sha256_file(copied_file),
        "page_count": len(pages),
        "full_text_path": str(run_dir / "full_text.txt"),
        "pages_path": str(run_dir / "pages.json"),
        "extraction_backend": backend,
    }
    write_json(run_dir / "manifest.json", manifest)
    write_json(base_dir / "data/metadata/runs" / f"{run_id}_document_{document_id}.json", manifest)
    return manifest
