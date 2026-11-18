from __future__ import annotations

import json
import math
import re
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

from ecosim.storage import ensure_project_layout, remove_and_recreate_dir, utc_timestamp, write_json

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text.lower())


def _strip_xml_tags(text: str) -> str:
    text = re.sub(r"</w:p>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return (
        text.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
    )


def _read_docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml").decode("utf-8", errors="ignore")
    return _strip_xml_tags(xml)


def _read_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return _read_docx_text(path)
    return path.read_text(encoding="utf-8", errors="ignore")


def _chunk_text(text: str, target_chars: int = 900) -> list[str]:
    paragraphs = [paragraph.strip() for paragraph in text.splitlines() if paragraph.strip()]
    if not paragraphs:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_size = 0
    for paragraph in paragraphs:
        if current and current_size + len(paragraph) > target_chars:
            chunks.append("\n".join(current))
            current = []
            current_size = 0
        current.append(paragraph)
        current_size += len(paragraph)
    if current:
        chunks.append("\n".join(current))
    return chunks


def _collect_sources(base_dir: Path) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    allowlist_path = base_dir / "configs/knowledge_documents.json"
    allowed_document_ids: set[str] = set()
    if allowlist_path.exists():
        payload = json.loads(allowlist_path.read_text(encoding="utf-8"))
        allowed_document_ids = set(payload.get("allowed_document_ids") or [])

    core_paths = [
        base_dir / "README.md",
        base_dir / "docs/phase1.md",
        base_dir / "docs/frontend_direction.md",
        base_dir / "data/processed/latest/overview.md",
        base_dir / "Plan_Detailed.docx",
    ]

    for path in core_paths:
        if path.exists():
            sources.append(
                {
                    "source_id": path.stem.lower().replace(" ", "_"),
                    "title": path.name,
                    "path": str(path),
                    "text": _read_text(path),
                }
            )

    documents_root = base_dir / "data/raw/documents"
    if documents_root.exists():
        for document_dir in sorted(path for path in documents_root.iterdir() if path.is_dir()):
            if allowed_document_ids and document_dir.name not in allowed_document_ids:
                continue
            runs = sorted(path for path in document_dir.iterdir() if path.is_dir())
            if not runs:
                continue
            latest_run = runs[-1]
            full_text = latest_run / "full_text.txt"
            if full_text.exists():
                sources.append(
                    {
                        "source_id": document_dir.name,
                        "title": f"{document_dir.name} document",
                        "path": str(full_text),
                        "text": full_text.read_text(encoding="utf-8", errors="ignore"),
                    }
                )
    return sources


def build_knowledge_index(base_dir: Path) -> dict[str, Any]:
    ensure_project_layout(base_dir)
    run_id = utc_timestamp()
    run_dir = base_dir / "data/knowledge" / run_id
    latest_dir = base_dir / "data/knowledge/latest"
    run_dir.mkdir(parents=True, exist_ok=True)
    remove_and_recreate_dir(latest_dir)

    sources = _collect_sources(base_dir)
    chunks: list[dict[str, Any]] = []
    doc_frequency: Counter[str] = Counter()

    for source in sources:
        source_chunks = _chunk_text(source["text"])
        for index, chunk_text in enumerate(source_chunks, start=1):
            tokens = _tokenize(chunk_text)
            if not tokens:
                continue
            term_freq = Counter(tokens)
            for token in term_freq:
                doc_frequency[token] += 1
            chunks.append(
                {
                    "chunk_id": f"{source['source_id']}::{index}",
                    "source_id": source["source_id"],
                    "title": source["title"],
                    "path": source["path"],
                    "text": chunk_text,
                    "term_frequency": dict(term_freq),
                    "token_count": len(tokens),
                }
            )

    index = {
        "run_id": run_id,
        "chunk_count": len(chunks),
        "source_count": len(sources),
        "document_frequency": dict(doc_frequency),
        "chunks": chunks,
    }
    write_json(run_dir / "index.json", index)
    write_json(latest_dir / "index.json", index)

    manifest = {
        "run_id": run_id,
        "index_path": str(run_dir / "index.json"),
        "latest_index_path": str(latest_dir / "index.json"),
        "chunk_count": len(chunks),
        "source_count": len(sources),
    }
    write_json(run_dir / "manifest.json", manifest)
    write_json(latest_dir / "manifest.json", manifest)
    return manifest


def load_knowledge_index(base_dir: Path) -> dict[str, Any]:
    path = base_dir / "data/knowledge/latest/index.json"
    if not path.exists():
        raise FileNotFoundError("Knowledge index not found. Run build-knowledge first.")
    return json.loads(path.read_text(encoding="utf-8"))


def search_knowledge(index: dict[str, Any], query: str, limit: int = 5) -> list[dict[str, Any]]:
    query_terms = _tokenize(query)
    if not query_terms:
        return []

    total_docs = max(index["chunk_count"], 1)
    df = index["document_frequency"]
    results: list[dict[str, Any]] = []

    for chunk in index["chunks"]:
        tf = chunk["term_frequency"]
        length_norm = 1.0 + math.log(max(chunk["token_count"], 1), 10)
        score = 0.0
        matched_terms = 0
        for term in query_terms:
            if term not in tf:
                continue
            matched_terms += 1
            idf = math.log((total_docs + 1) / (1 + df.get(term, 0))) + 1.0
            score += (tf[term] / length_norm) * idf
        if score <= 0:
            continue
        results.append(
            {
                "chunk_id": chunk["chunk_id"],
                "source_id": chunk["source_id"],
                "title": chunk["title"],
                "path": chunk["path"],
                "text": chunk["text"],
                "score": round(score + matched_terms * 0.05, 4),
            }
        )

    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:limit]
