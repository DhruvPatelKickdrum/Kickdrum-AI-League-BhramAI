# Real-Time News Claim Verification Assistant

An agentic RAG (Retrieval-Augmented Generation) system that verifies user claims by gathering evidence from a static knowledge base and live web sources, then producing a transparent verdict with citations.

## Architecture

```
User Claim
    │
    ▼
┌───────────────────┐
│  LangGraph Agent   │ ← Agentic orchestration with multi-step reasoning
│  (Reasoning Loop)  │
└────────┬──────────┘
         │
    ┌────┴────┐
    │  Router  │ ← LLM classifies: static / dynamic / invalid
    └────┬────┘
         │
    ┌────┴──────────────────┐
    │                       │
    ▼                       ▼
┌──────────┐        ┌──────────────┐
│ Static   │        │ Dynamic      │
│ pgvector │        │ Scrapers     │
│ + Rerank │        │ (News, Fin,  │
└────┬─────┘        │  Govt, Wx)   │
     │              └──────┬───────┘
     │                     │
     └─────────┬───────────┘
               │
          ┌────┴─────┐
          │ Verify   │ ← Cross-check + NLI-style verdict
          │ & Store  │ ← Store stable facts back to pgvector
          └────┬─────┘
               │
          ┌────┴─────┐
          │ Synthesis │ ← Verdict + Reasoning + Citations
          └──────────┘
```

## Features

- **Agentic RAG**: Multi-step reasoning with self-correction, re-querying, and multi-source consensus
- **Query Router**: LLM-based classification (static/dynamic/invalid) with domain detection
- **Static KB**: pgvector with HNSW indexing + cross-encoder reranking
- **Dynamic Sources**: BBC News, ANI, Livemint, RBI, IBEF, Open-Meteo weather
- **Fact Storage**: LLM-normalized facts stored with deduplication
- **Transparent Reasoning**: Full agent reasoning trace in responses

## Quick Start

**For a step-by-step testing checklist, see [TESTING.md](TESTING.md).**

### Prerequisites

- Python 3.11+
- Docker (for Postgres + pgvector)
- OpenAI API key (real key required; web search uses the Responses API)

### Setup

```bash
# 1. Clone and enter the project
cd 01AILeague

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy and edit environment variables
cp .env.example .env
# Edit .env with your OpenAI API key

# 5. Start Postgres with pgvector
docker-compose up -d

# 6. Initialize the database
python scripts/setup_db.py

# 7. Ingest EU AI Act data into the knowledge base
python scripts/ingest_data.py
```

### Usage

```bash
# CLI
python cli.py "The EU AI Act bans social scoring systems."

# With verbose logging
python cli.py --verbose "What is the current inflation rate in India?"

# With agent reasoning trace
python cli.py --trace "Is it raining in Mumbai?"

# Programmatic
python main.py "Who won the 2024 US election?"
```

### Programmatic API

```python
from main import verify_claim

result = verify_claim("The EU AI Act classifies AI into risk categories.")
print(result["verdict"])          # "Supported"
print(result["formatted_response"])  # Full formatted response with citations
print(result["reasoning_trace"])  # Agent's step-by-step reasoning
```

## Project Structure

```
01AILeague/
├── config/              # Settings and logging configuration
├── src/
│   ├── agent/          # LangGraph agent, tools, prompts
│   ├── core/           # Router, embeddings, reranker, verification
│   ├── retrieval/      # Static (pgvector) and dynamic retrieval
│   ├── scrapers/       # Domain-specific scrapers (news, finance, govt, weather)
│   ├── ingestion/      # Docling parser, chunker, vectorizer
│   ├── database/       # SQLAlchemy models, connection, operations
│   └── utils/          # Text processing, hashing, validators
├── scripts/            # DB setup and data ingestion scripts
├── tests/              # Pytest test suite
├── cli.py              # CLI entry point
├── main.py             # Programmatic entry point
└── docker-compose.yml  # Postgres + pgvector
```

## Technical Details

- **Embedding Model**: OpenAI `text-embedding-3-small` (1536 dims)
- **Vector DB**: PostgreSQL + pgvector with HNSW indexes
- **Chunking**: 512 tokens with 50-token overlap
- **Reranking**: `cross-encoder/ms-marco-MiniLM-L-6-v2`
- **LLM**: OpenAI GPT-4o-mini (routing + synthesis)
- **Agent Framework**: LangGraph (multi-step reasoning with tool use)
- **Initial KB**: EU AI Act website (parsed via Docling)

## Running Tests

```bash
pytest tests/ -v
```

## Data Sources

| Domain     | Sources                    | Type        |
|------------|----------------------------|-------------|
| Static KB  | pgvector (EU AI Act, etc.) | Vector DB   |
| News       | BBC News, ANI              | Web scrape  |
| Finance    | Livemint                   | Web scrape  |
| Government | RBI, IBEF                  | Web scrape  |
| Weather    | Open-Meteo                 | Free API    |
