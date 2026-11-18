# Eco Sim

Eco Sim is now a runnable local application.

It does five things in one repo:
- collects and preserves source data
- builds a processed macro snapshot
- runs a transparent policy scenario engine
- retrieves grounded project context from a local knowledge index
- serves a frontend that maps persona outcomes onto an isometric colony view

This build is intentionally conservative about system risk:
- Python standard library first
- no database server
- no heavy ML runtime
- no Docker requirement
- no hidden cloud dependency

The simulation model is transparent heuristic logic anchored to real baseline data, not a causal model with policy-identification claims.

## What Exists Now

### 1. Data collection layer

Implemented in:
- ecosim/sources/world_bank.py
- ecosim/sources/manual.py
- ecosim/documents.py

Current behavior:
- World Bank indicators are collected automatically and stored as immutable timestamped runs.
- The collector now uses the V2 Indicators API explicitly against World Development Indicators (`source=2`) with retry logic and browser-like request headers because the endpoint can be intermittently flaky.
- If a live fetch fails for one indicator but an older raw payload exists locally, the run can reuse that cached indicator and finish with warnings instead of crashing halfway through.
- Curated or licensed datasets are manually registered with checksums and manifests instead of being scraped badly.
- PDF documents can be ingested and text-extracted for later retrieval.

Why:
- stable public APIs should be automated
- brittle scraping should not be the foundation of a policy product
- provenance matters because later model behavior depends on source trust
- partial progress should not be thrown away because one external API request times out

### 2. Processed data layer

Implemented in:
- ecosim/processing.py

Current behavior:
- loads the latest World Bank raw run
- pivots the historical series
- computes latest values, trailing averages, slopes, and volatility
- derives macro baseline composites like fiscal stress, investment sentiment, household pressure, exchange stability, and trade momentum
- writes a processed snapshot and overview into `data/processed/latest/`

Important modeling decision:
- the processed layer separates raw indicators from product-facing macro composites
- this gives the UI and model stable fields even when raw source structure evolves

### 3. Scenario engine

Implemented in:
- ecosim/model.py
- configs/policy_model.json
- configs/colony_entities.json

The scenario engine uses:
- baseline macro values from the processed snapshot
- a configurable policy lever catalog
- explicit policy-to-metric weights
- horizon-sensitive lever multipliers for `1`, `5`, and `10` year views
- persona formulas for `LIG`, `MIG`, `HIG`, `farmers`, `MSMEs`, `public services`, and `market activity`

Policy levers currently implemented:
- income tax rate
- GST rate
- policy rate
- capital spending
- welfare spending
- subsidy support
- credit support
- export push
- infrastructure push
- debt discipline

Macro metrics currently exposed:
- GDP growth
- inflation
- unemployment
- fiscal stress
- investment sentiment
- exchange stability
- trade momentum
- household pressure

Important honesty point:
- the lever weights are explicit heuristics
- they are readable and editable
- they are not learned from enough policy-outcome data to justify causal confidence

That is still the right engineering choice at this stage because:
- the repo does not yet contain a robust cross-source policy history dataset
- pretending otherwise would just hide guesswork behind fake sophistication

### 4. Local retrieval / explanation layer

Implemented in:
- ecosim/knowledge.py
- ecosim/service.py
- configs/knowledge_documents.json

Current behavior:
- indexes local Markdown, DOCX, processed overview, and allowed extracted documents
- chunks them into search units
- builds a lightweight lexical relevance index
- returns citations with file paths and excerpts
- uses those citations to support deterministic scenario summaries

What it is:
- retrieval-backed explanation

What it is not:
- a full LLM-powered RAG stack

Why:
- local, dependency-light, and testable is better than bolting on a brittle model dependency too early

### 5. Backend application

Implemented in:
- ecosim/server.py
- ecosim/service.py
- ecosim/cli.py

The backend is a local WSGI app served with the Python standard library. That was intentional.

Why this backend choice is good here:
- no framework install required
- small surface area
- no background services
- easy to test directly
- low system risk

API routes:
- `GET /api/health`
- `GET /api/config`
- `GET /api/baseline`
- `POST /api/simulate`
- `POST /api/explain`
- `GET /api/knowledge/search?q=...`

### 6. Frontend application

Implemented in:
- web/index.html
- web/styles.css
- web/app.js
- Frontend_Reference.jpg

Frontend decisions:
- no framework
- no build step
- no package manager dependency
- the same local server serves API and static assets

UI behavior:
- the reference image is the colony surface
- personas are positioned as anchored scene markers with visible callout labels
- each callout is connected back to its building cluster with SVG guide lines
- desktop labels are pushed toward the scene edges so the artwork stays readable instead of being covered by large floating boxes
- center-weighted entities can fall into a dedicated rail below the image instead of forcing another card onto the roofs
- policy levers are controlled from a left-side panel
- macro results update in a metric strip
- clicking a label or navigator card opens a modal impact window for that persona
- each impact window filters to persona metrics plus only the macro metrics relevant to that persona
- the right-side column is now a navigator, not the main detail surface
- technical summary pulls a grounded explanation with citations

Design direction adopted:
- warm civic palette instead of generic white-purple dashboard styling
- serif headings plus non-default sans body type
- glass/paper panels over a textured background
- colony view as the hero, not a dashboard grid
- map labels are intentionally high-contrast and readable without hover
- mobile falls back to a label rail below the scene instead of hiding interaction behind tiny overlays

## Project Structure

Key files:
- ecosim/cli.py: entry point for data, build, and server commands
- ecosim/storage.py: filesystem layout and artifact helpers
- ecosim/processing.py: processed snapshot builder
- ecosim/model.py: scenario engine
- ecosim/knowledge.py: local retrieval index
- ecosim/service.py: application service layer
- ecosim/server.py: WSGI app and local server
- configs/world_bank_india.json: automated World Bank source config
- configs/source_registry.json: managed manual source registry
- configs/policy_model.json: policy lever and macro metric catalog
- configs/colony_entities.json: persona catalog and scene positions
- configs/knowledge_documents.json: allowed extracted docs for knowledge indexing

## Commands

### Bootstrap directories

```bash
python3 -m ecosim bootstrap
```

### Collect World Bank data

```bash
python3 -m ecosim collect-world-bank --config configs/world_bank_india.json
```

### Register a manual dataset

```bash
python3 -m ecosim register-manual \
  --registry configs/source_registry.json \
  --source-id sdg_india_index \
  --file /absolute/path/to/file.csv
```

### Extract a PDF document

```bash
python3 -m ecosim extract-document \
  --document-id indian-economy-reference \
  --file /absolute/path/to/book.pdf
```

### Build the processed snapshot

```bash
python3 -m ecosim prepare-data
```

### Build the retrieval index

```bash
python3 -m ecosim build-knowledge
```

### Extract SDG report PDFs into CSV

This command is for the specific SDG India report layouts currently supported in this repo:
- `SDG-India-Index-2021.pdf` -> report cycle `2019-20`
- `SDG_India_Index_2020.pdf` -> report cycle `2020-21`
- `SDA_INDIA_INDEX_2023.pdf` -> report cycle `2023-24`

Run it on the whole `sdg/` directory:

```bash
python3 -m ecosim extract-sdg --input-dir sdg
```

Outputs:
- `data/processed/sdg/latest/2019_20_goal_scores.csv`
- `data/processed/sdg/latest/2020_21_goal_scores.csv`
- `data/processed/sdg/latest/2023_24_goal_scores.csv`
- `data/processed/sdg/latest/combined_goal_scores_wide.csv`
- `data/processed/sdg/latest/combined_goal_scores_long.csv`

What this does:
- rows are cleaned and normalized
- split UT names are repaired
- all report tables are mapped to a common `sdg_1 ... sdg_16` schema
- `row_type` identifies `state`, `union_territory`, `india`, or `target`

This workflow needs `tabula-py` plus Java. In this version, that is treated as an optional SDG extraction dependency.

### Run the app

```bash
python3 -m ecosim serve
```

### Enable live evidence with Tavily

Set `TAVILY_API_KEY` in the local `.env` file. Each multi-agent assessment then lets the Evidence Agent retrieve current web and news sources with Tavily, alongside the local knowledge index. Live search is optional: when the key or network is unavailable, assessments continue with local citations.

```text
TAVILY_API_KEY=your_tavily_key
```

Open:

```text
http://127.0.0.1:8000
```

## Data Layout

```text
data/
  raw/
    world_bank/
    manual/
    documents/
  processed/
    latest/
    <timestamp>/
  knowledge/
    latest/
    <timestamp>/
  metadata/
    runs/
```

Principles behind this layout:
- raw runs remain immutable
- processed and knowledge artifacts are rebuilt snapshots
- `latest/` is a runtime convenience alias
- manifests exist so you can inspect what produced what

## Modeling Concepts Adopted

These are the core concepts currently used in the product.

### Transparent simulation over opaque pseudo-ML

Adopted:
- explicit levers
- explicit weights
- explicit horizon adjustments
- explicit clamping rules
- explicit persona formulas

Rejected for now:
- throwing an LSTM at annual macro data
- claiming predictive validity without enough policy history
- hiding weak assumptions behind a black-box API

### Local retrieval over premature LLM dependency

Adopted:
- chunked local documents
- lexical ranking
- deterministic summaries
- citations with source paths

Rejected for now:
- ungrounded free-text generation
- external model calls for core explanation behavior

### Local-first runtime over distributed complexity

Adopted:
- one local Python process
- static frontend
- filesystem artifacts
- standard-library WSGI server

Rejected for now:
- container orchestration
- database clusters
- queueing infrastructure
- multiple microservices

## Testing

Tests cover:
- manual intake behavior
- World Bank normalization
- processed snapshot generation
- scenario engine behavior
- knowledge indexing and search
- server route behavior

Run all tests:

```bash
python3 -m unittest discover -s tests
```

## Current Limits

- The model is not yet calibrated against a defensible policy-response training dataset.
- Some baseline indicators are stale because the available World Bank series are stale.
- Manual sources are registered but not yet harmonized into a richer multi-source policy warehouse.
- The explanation system is grounded, but it is template-based rather than LLM-generated.
- The frontend is elegant and functional, but it is still a no-build static app rather than a large component system.

## What is done:

- the whole stack runs locally
- the data path is auditable
- the model assumptions are visible
- the UI is not generic
- the tests are real

## Future Works:

1. Add official RBI / MOSPI / Union Budget structured sources and harmonize them in the processed layer.
2. Replace heuristic policy weights with a documented econometric or constrained regression workflow.
3. Add model versioning and comparative backtesting reports.
4. Introduce a richer document corpus for the explanation layer.
5. Move the frontend from hotspot overlay to a richer scene engine only if the map complexity actually justifies it.

## Verification Status

- data collection already present in the repo
- processed snapshot build
- knowledge index build
- scenario simulation calls
- explanation generation
- automated unit tests
