# ArthaNiti

**An economic policy simulation and decision-support platform for exploring policy trade-offs and their impact on different socioeconomic groups.**

ArthaNiti combines real-world economic data, transparent policy modeling, personalized impact analysis, knowledge retrieval, and multi-agent assessment to help users understand the potential consequences of economic policy decisions.

---

## Overview

ArthaNiti allows users to experiment with economic policy changes and explore their potential effects on macroeconomic indicators, households, and economic sectors across multiple time horizons.

The platform integrates historical economic data, configurable policy levers, persona-based impact calculations, contextual knowledge retrieval, and an interactive visualization interface.

## Key Features

- **Economic Data Pipeline:** Collects World Bank indicators and manages curated datasets with source provenance.
- **Policy Scenario Simulation:** Models changes in taxation, interest rates, subsidies, welfare, infrastructure, credit support, and other policy levers.
- **Multi-Horizon Analysis:** Evaluates scenarios across 1-year, 5-year, and 10-year horizons.
- **Multi-Agent Assessment:** Uses specialized agents for Citizen, Economic, Policy, Risk, and Evidence analysis.
- **Personalized Impact Analysis:** Evaluates policy outcomes for low-, middle-, and high-income households, farmers, MSMEs, public services, and market activity.
- **Knowledge Retrieval:** Retrieves relevant information from indexed documents and provides source citations.
- **Explainable Modeling:** Uses configurable policy-to-metric relationships to make simulation assumptions transparent.
- **Interactive Visualization:** Presents policy outcomes through an interactive frontend featuring an isometric economic colony visualization.

## System Architecture

### 1. Data Collection
- Automated collection of economic indicators from the World Bank.
- Support for curated and manually registered datasets.
- PDF document ingestion and text extraction.
- Timestamped raw data storage and source manifests.

### 2. Data Processing
- Historical indicator normalization and transformation.
- Calculation of latest values, averages, trends, and volatility.
- Generation of macroeconomic baseline composites.

### 3. Policy Simulation Engine
- Configurable policy levers and policy-to-metric weights.
- Horizon-sensitive impact calculations.
- Persona-specific impact formulas.
- Scenario comparison against baseline economic conditions.

### 4. Knowledge and Evidence Layer
- Local document indexing and chunking.
- Lightweight lexical retrieval.
- Citation-backed context and source excerpts.
- Optional live evidence retrieval through Tavily.

### 5. Application and Visualization Layer
- Python-based backend using WSGI.
- Static frontend with interactive policy controls.
- Macroeconomic metric visualization.
- Persona-specific impact windows and contextual explanations.

## Policy Variables

The simulation currently supports policy levers such as:

- Income tax rate
- GST rate
- Policy interest rate
- Capital expenditure
- Welfare spending
- Subsidies
- Credit support
- Export promotion
- Infrastructure investment
- Debt discipline

## Economic Indicators

Scenario outcomes are evaluated using indicators including:

- GDP growth
- Inflation
- Unemployment
- Fiscal stress
- Investment sentiment
- Exchange stability
- Trade momentum
- Household pressure

## Technology Stack

| Component | Technology |
|---|---|
| Backend | Python |
| Data Sources | World Bank API, curated datasets |
| Data Processing | Python data processing pipeline |
| Storage | Filesystem, SQLite where applicable |
| Knowledge Retrieval | Local indexing and lexical search |
| AI Assessment | Multi-agent orchestration, LLM integrations |
| Live Evidence | Tavily (optional) |
| Frontend | HTML, CSS, JavaScript |
| Backend Server | WSGI, Python standard library |

## Project Structure

```text
ArthaNiti/
├── ecosim/
│   ├── cli.py
│   ├── storage.py
│   ├── processing.py
│   ├── model.py
│   ├── knowledge.py
│   ├── service.py
│   ├── server.py
│   ├── documents.py
│   └── sources/
├── configs/
│   ├── world_bank_india.json
│   ├── source_registry.json
│   ├── policy_model.json
│   ├── colony_entities.json
│   └── knowledge_documents.json
├── data/
│   ├── raw/
│   ├── processed/
│   ├── knowledge/
│   └── metadata/
├── web/
│   ├── index.html
│   ├── styles.css
│   └── app.js
└── tests/
```

## Getting Started

### Prerequisites

- Python 3.10+
- Git

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/ArthaNiti.git
cd ArthaNiti
```

### 2. Initialize the project

```bash
python -m ecosim bootstrap
```

### 3. Collect economic data

```bash
python -m ecosim collect-world-bank --config configs/world_bank_india.json
```

### 4. Prepare the processed data

```bash
python -m ecosim prepare-data
```

### 5. Build the knowledge index

```bash
python -m ecosim build-knowledge
```

### 6. Start the application

```bash
python -m ecosim serve
```

Open your browser and navigate to:

```text
http://127.0.0.1:8000
```

## Optional: Live Evidence Retrieval

To enable live web evidence retrieval for multi-agent assessments, configure your Tavily API key in a local `.env` file:

```env
TAVILY_API_KEY=your_tavily_api_key
```

Live retrieval is optional. The platform can continue using its local knowledge sources when live search is unavailable.

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | Health check |
| GET | `/api/config` | Retrieve application configuration |
| GET | `/api/baseline` | Retrieve baseline economic indicators |
| POST | `/api/simulate` | Run a policy simulation |
| POST | `/api/explain` | Generate a grounded scenario explanation |
| GET | `/api/knowledge/search?q=...` | Search the local knowledge index |

## Testing

Run the test suite:

```bash
python -m unittest discover -s tests
```

Tests cover data intake, World Bank normalization, data processing, scenario simulation, knowledge retrieval, and server routes.

## Modeling Approach

ArthaNiti uses a transparent, configurable heuristic-based simulation model anchored to real economic baseline data.

Policy levers are connected to economic metrics through explicit weights, horizon adjustments, and persona-specific formulas. These relationships are editable and designed to make assumptions inspectable.

**The simulation is exploratory rather than predictive.** Its outputs represent modeled scenarios and potential trade-offs, not definitive causal estimates of real-world policy outcomes.

## Future Improvements

- Integrate additional official economic data sources such as RBI and MOSPI.
- Develop a more rigorous econometric modeling pipeline.
- Introduce model versioning and backtesting.
- Expand the knowledge corpus.
- Improve comparative policy analysis.

---

*ArthaNiti — Exploring economic policies, trade-offs, and their impact on people.*
