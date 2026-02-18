# Testing the Claim Verification Pipeline

This guide lists exactly what you need to set up and the order to run things so you can test the pipeline.

---

## 1. Prerequisites

| Requirement | Purpose |
|-------------|---------|
| **Python 3.11+** | Runtime |
| **Docker** | Postgres + pgvector (or use a hosted Postgres with pgvector) |
| **OpenAI API key** | LLM, embeddings, and web search (`client.responses.parse` with `web_search`) |

---

## 2. One-time setup

Run these in order from the project root (`01AILeague/`).

### Step 1: Virtual environment and dependencies

```bash
cd 01AILeague
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Step 2: Environment variables

You already have `.env`. Update it with:

- **`OPENAI_API_KEY`** — A **real** key (not the dummy). Needed for:
  - Router, verification, synthesis (Chat Completions)
  - Embeddings (`text-embedding-3-small`)
  - Web search (`client.responses.parse` with `web_search` tool)

Leave `DATABASE_URL` as-is if you use local Docker Postgres.

### Step 3: Start Postgres with pgvector

```bash
docker-compose up -d
```

Wait a few seconds, then check:

```bash
docker-compose ps
```

### Step 4: Initialize the database

```bash
python scripts/setup_db.py
```

This creates the `pgvector` extension and the `documents` and `facts` tables.

### Step 5 (optional but recommended): Ingest static knowledge base

To test **static** claims (e.g. about the EU AI Act), seed the KB:

```bash
python scripts/ingest_data.py
```

This uses **Docling** to parse the EU AI Act website and fill the `documents` table. It can take a couple of minutes and requires network access.

---

## 3. Run tests

### Unit tests (no API key or DB required for most)

```bash
pytest tests/ -v
```

Some tests mock OpenAI. Tests that hit the DB (e.g. search) need Postgres running.

### CLI: verify a claim

```bash
python cli.py "The EU AI Act bans social scoring systems."
```

With verbose logs and agent trace:

```bash
python cli.py --verbose --trace "What is the current weather in Mumbai?"
```

### Programmatic

```bash
python main.py "The EU AI Act classifies AI into risk categories."
```

Or from Python:

```python
from main import verify_claim
result = verify_claim("The EU AI Act bans social scoring.")
print(result["verdict"], result["formatted_response"])
```

---

## 4. Is it ready to test?

| Component | Ready? | Notes |
|-----------|--------|--------|
| **Config** | Yes | `config/settings.py`, `config/sources.yaml` — no code changes needed to add domains. |
| **Database** | Yes | After `docker-compose up -d` and `python scripts/setup_db.py`. |
| **Static KB** | Yes | After `python scripts/ingest_data.py` (Docling + EU AI Act URLs). |
| **Router / verification / synthesis** | Yes | Uses standard Chat Completions + your `OPENAI_API_KEY`. |
| **Web search (dynamic)** | Yes* | Uses `client.responses.parse` with `web_search` and `allowed_domains` from `sources.yaml`. Requires an API key with access to the **Responses API** and **web search**. If you get errors here, check [OpenAI Responses API](https://platform.openai.com/docs/api-reference/responses) and [Web search guide](https://platform.openai.com/docs/guides/tools-web-search). |
| **Weather** | Yes | Open-Meteo is called directly (no key). URL is configurable in `config/sources.yaml`. |

So: **yes, it’s ready to test** once you:

1. Use a **real** `OPENAI_API_KEY` in `.env`.
2. Run **Steps 1–4** above (venv, deps, Docker, `setup_db.py`).
3. Optionally run **Step 5** (`ingest_data.py`) for static EU AI Act claims.

---

## 5. Quick sanity checks

- **Config loads:**  
  `python -c "from config.settings import get_allowed_domains; print(get_allowed_domains('news'))"`  
  Should print something like `['bbc.com', 'aninews.in']`.

- **DB connects:**  
  `python scripts/setup_db.py`  
  Should print “Database initialized successfully!”.

- **Static search (after ingest):**  
  `python -c "
  from src.retrieval.static import search_static_kb
  r = search_static_kb('EU AI Act risk categories')
  print('above_threshold', r['above_threshold'], 'results', len(r['results']))
  "`

- **Weather (no key):**  
  `python -c "
  from src.retrieval.dynamic import search_dynamic
  r = search_dynamic('weather in Delhi', domain='weather')
  print(len(r), r[0]['content'][:80] if r else 'no results')
  "`

---

## 6. Troubleshooting

- **`responses.parse` or web search errors**  
  Your key may not have Responses API / web search access. Check the [OpenAI docs](https://platform.openai.com/docs/guides/tools-web-search) and your account/model access.

- **Docling fails on ingest**  
  Ensure you have network access and that the EU AI Act URLs in `scripts/ingest_data.py` are reachable. You can still test dynamic (web search, weather) and router/verification without ingesting.

- **“No module named 'pgvector'” or DB errors**  
  Run `pip install -r requirements.txt` and ensure Postgres is up (`docker-compose ps`) and `DATABASE_URL` in `.env` matches your container (e.g. `postgresql://postgres:postgres@localhost:5432/claim_verifier`).

- **Reranker slow on first run**  
  The first call downloads `cross-encoder/ms-marco-MiniLM-L-6-v2`; later runs are faster.
