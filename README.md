# Competitive Intelligence Engine

Tracks companies, people, and topics across multiple sources and lets you query the accumulated signals in plain English.

The core idea: instead of asking an LLM what it knows about a company, you continuously ingest real data (job postings, HN discussions, news, GitHub activity, arXiv papers), extract structured signals from it, and build a queryable knowledge base that grows over time. The query interface is a ReAct agent that picks between semantic search and structured SQL depending on what you ask.

## What it does

- Ingests from HN, NewsAPI, Greenhouse, Lever, GitHub, and arXiv on a configurable schedule
- Extracts typed signals (hiring, product, research, funding, mention) via Claude Haiku, batched per crawl
- Embeds signals with Voyage AI (voyage-3, 1024 dims) using a single batched API call per extraction run
- Answers natural language questions with a Claude Sonnet ReAct agent that chooses between semantic search, SQL lookup, and report fetch
- Deduplicates signals by content hash before writing to the DB
- Generates weekly digest reports per target
- Fires webhook alerts on configurable conditions

## Stack

- **Backend**: FastAPI + SQLAlchemy (asyncpg) + PostgreSQL + pgvector
- **Task queue**: Celery + Redis
- **LLMs**: Anthropic (Sonnet for queries, Haiku for extraction)
- **Embeddings**: Voyage AI (voyage-3, 1024 dims) with Redis cache, OpenAI as fallback
- **Frontend**: Next.js + Tailwind

## Setup

```bash
# Python dependencies
pip install -e ".[dev]"

# Frontend dependencies
cd frontend && npm install

# Copy and fill in env vars
cp .env.example .env

# Start Postgres and Redis, then run migrations
alembic upgrade head
```

Required keys: `ANTHROPIC_API_KEY`, `VOYAGE_API_KEY`. Everything else is optional but limits which sources work.

```bash
# API
uvicorn api.main:app --reload

# Frontend
cd frontend && npm run dev

# Celery worker (needs both queues)
celery -A tasks.celery_app worker -Q crawl,llm --loglevel=info
```

## Adding a target

Targets can be added through the UI or via the API. Each target has a `sources` config that controls what gets crawled and a `schedule` that controls how often.

```bash
curl -X POST http://localhost:8000/targets \
  -H "X-API-Key: changeme-dev-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme Corp",
    "type": "company",
    "sources": {
      "hn":         {"query": "Acme Corp", "include_hiring": true},
      "news":       {"query": "Acme Corp"},
      "lever":      {"slug": "acmecorp"},
      "greenhouse": {"slug": "acmecorp"}
    },
    "schedule": {
      "hn": "6h",
      "news": "6h",
      "lever": "daily",
      "greenhouse": "daily"
    }
  }'
```

Then trigger an initial crawl (or use the "Trigger crawl" button in the UI):

```bash
curl -X POST http://localhost:8000/runs/trigger/{target_id} \
  -H "X-API-Key: changeme-dev-key"
```

## Notes

The product gets more useful with signal volume. Semantic search starts returning meaningfully differentiated results around 50+ signals per target. With multiple targets and a few weeks of data, the query agent can surface hiring patterns, product direction shifts, and cross-company comparisons that aren't available from any single LLM call.
