# Phase 1 Architecture

## Goal

Build a reproducible ingestion layer that can be trusted by later model and backend work.

## Decisions

1. Automate only stable public interfaces.
2. Keep raw data immutable per run.
3. Store manifests for every intake event.
4. Separate manual intake from automated collection so provenance stays obvious.
5. Treat document extraction as preparation for Phase 2, not as full RAG.

## Implemented workflows

### 1. World Bank collection

Command:

```bash
python3 -m ecosim collect-world-bank --config configs/world_bank_india.json
```

Writes:
- per-indicator raw JSON responses
- `records.csv` with normalized rows
- `manifest.json` with counts and runtime metadata

### 2. Manual dataset intake

Command:

```bash
python3 -m ecosim register-manual \
  --registry configs/source_registry.json \
  --source-id sdg_india_index \
  --file /path/to/export.csv
```

Writes:
- copied source file
- SHA-256 checksum
- source metadata from the registry

Use this for:
- SDG India Index exports
- budget tables
- licensed research tables
- any source that should not be scraped blindly

### 3. Document extraction

Command:

```bash
python3 -m ecosim extract-document \
  --document-id indian-economy-reference \
  --file /path/to/book.pdf
```

Writes:
- copied source PDF
- `pages.json`
- `full_text.txt`
- manifest with page counts and extraction backend

The extractor will use `PyMuPDF`, `pypdf`, or system binaries `pdftotext` + `pdfinfo`, whichever is available first.

## Recommended next step after Phase 1

Phase 2 should read from:
- `data/raw/world_bank/<run-id>/records.csv`
- `data/raw/manual/<source-id>/<run-id>/`
- `data/raw/documents/<document-id>/<run-id>/full_text.txt`

Then add:
- schema validation
- dataset harmonization
- chunking and embedding prep
- a stable simulation input schema
