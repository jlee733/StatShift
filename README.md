# StatShift

Local fantasy football statistics assistant. Query seeded NFL/fantasy data through a read-only API, or chat with a local LLM for open-ended analysis.

**Streamlit** → **RAG** → **FastAPI (read-only)** → **SQLite**  
**RAG** → **Ollama** → **Gemma**

Factual questions (stats, matchups, injuries) are answered from the database. Conversational prompts go to Gemma.

## Project layout

| Package | Role |
|---------|------|
| `ui/` | Streamlit app (`ui/app.py`) and pages |
| `api/` | FastAPI read-only HTTP service |
| `db/` | SQLite schema, read access, scrape loaders |
| `espn/` | ESPN client, player research, bulk scrape |
| `jobs/` | Prefect ingestion flows |
| `draft/` | Mock draft engine and player pools |
| `rag/` | Intent routing and Ollama Q&A |
| `scripts/` | DB init and sync CLIs |

## Prerequisites

- **Docker (recommended):** Docker Desktop or Docker Engine with Compose v2
- **Or local Python 3.11+** and [Ollama](https://ollama.com) with Gemma (`ollama pull gemma2:2b`)

The Docker image includes R, [ffanalytics](https://github.com/FantasyFootballAnalytics/ffanalytics), and `rpy2` for the Mock Draft tab — no separate R install when using Compose.

## Run with Docker

```bash
docker compose up --build
```

First startup pulls `gemma2:2b` into the Ollama container (can take a few minutes). Then open:

**http://localhost:8501**

Optional: API docs at http://localhost:8000/docs

```bash
# Stop
docker compose down

# Reset DB + models (re-seeds fantasy football sample data)
docker compose down -v
```

Services:

| Service | Role | Host port |
|---------|------|-----------|
| `ui` | Streamlit (your browser connects here) | 8501 |
| `api` | FastAPI read-only API | 8000 |
| `ollama` | Gemma inference | 11434 |

Inside the Compose network, the UI talks to `http://api:8000` and `http://ollama:11434`.

## Local setup (without Docker)

```bash
cd StatShift
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/init_db.py
```

## Run (three terminals)

```bash
# 1 — API
uvicorn api.main:app --reload

# 2 — UI
streamlit run ui/app.py

# 3 — Ollama (if not already running)
ollama serve
```

Or use helper scripts:

```bash
chmod +x scripts/run_api.sh scripts/run_ui.sh
./scripts/run_api.sh
./scripts/run_ui.sh
```

Open http://127.0.0.1:8501 and ask about players, weekly matchups, injuries, or PPR scoring from the seeded data.

If you previously ran an older build with different seed data, delete `data/statshift.db` or run `docker compose down -v` before re-initializing.

## Mock Draft (Docker Compose)

With the stack running (`docker compose up --build`), open **http://localhost:8501** → **Mock Draft**. The player pool comes from **ffanalytics** (projections for Standard / Half-PPR / PPR plus ADP). R and ffanalytics are already in the `ui` image.

The cache lives in the **`statshift_data` volume** at `/app/data/ffanalytics_players.json` (24-hour TTL). It survives container restarts until you run `docker compose down -v`.

**First visit:** opening Mock Draft or clicking **Refresh player pool** triggers a scrape (often several minutes). **Later visits** use the cache.

Optional — pre-warm the cache before using the UI:

```bash
# One-off sync service (stack does not need to be up)
docker compose --profile sync run --rm ffanalytics-sync

# Or, while ui is running
docker compose exec ui python scripts/sync_ffanalytics_players.py
```

After rebuilding the image (`docker compose up --build`), run a sync again if ffanalytics or R packages changed.

## ESPN player scrape → SQLite

Active NFL players (injuries + recent game logs) can be scraped from ESPN and loaded into the same SQLite file the API uses (`data/statshift.db`).

### Prefect server + scrape (recommended)

Run a **local Prefect server** (UI at http://127.0.0.1:4200), then run the scrape against it. Scripts use **`caffeinate`** on macOS so the Mac stays awake during the job (plug in AC power).

```bash
chmod +x scripts/start_prefect_server.sh scripts/run_espn_scrape_prefect.sh scripts/run_espn_scrape_background.sh

# Start Prefect (Docker, detached)
./scripts/start_prefect_server.sh

# Run scrape in foreground (prevents sleep on macOS)
./scripts/run_espn_scrape_prefect.sh

# Or background + log (starts Prefect if needed)
./scripts/run_espn_scrape_background.sh
```

**Docker:**

```bash
docker compose --profile prefect up -d prefect-server
docker compose --profile prefect --profile sync run --rm espn-active-sync
```

Flows use `PREFECT_API_URL=http://127.0.0.1:4200/api` (stable UI/API, not a random ephemeral port). Telemetry is disabled via `PREFECT_SERVER_ANALYTICS_ENABLED=false`.

### Without Prefect

```bash
python -m jobs.scrape_active_players_sync
```

### Reload DB only

```bash
python scripts/load_players_to_db.py
```

`GET /health` reports `player_count` and `last_scrape_at` after a load.

With `ESPN_API_DELAY_SECONDS=30`, a full scrape can take **many hours**. Per-letter JSON is written under `data/espn_active_by_letter/` as each letter completes.

## Tests

```bash
python -m unittest discover -s tests -v
```

CI runs the same suite on pull requests and pushes to `main` (ffanalytics parsing tests do not call R).

## Configuration

Optional `.env` overrides:

```env
OLLAMA_MODEL=gemma2:2b
OLLAMA_BASE_URL=http://127.0.0.1:11434
API_BASE_URL=http://127.0.0.1:8000
ESPN_API_DELAY_SECONDS=30
PREFECT_API_URL=http://127.0.0.1:4200/api
PREFECT_SERVER_ANALYTICS_ENABLED=false
```

## API (read-only)

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Service + DB check (`player_count`, `last_scrape_at`) |
| `GET /documents` | List documents |
| `GET /documents/{id}` | Single document |
| `GET /search?q=...` | FTS search for RAG |
| `GET /categories` | Distinct categories |
| `GET /players` | List scraped players (`letter`, `limit`, `offset`) |
| `GET /players/search?q=...` | Search players by name |
| `GET /players/{espn_id}` | Player profile, injuries, game logs |

`POST`, `PUT`, `PATCH`, and `DELETE` return **405** — writes are blocked at the API layer; SQLite is opened in read-only mode for queries.

## Sample data categories

| Category | Examples |
|----------|----------|
| `player` | McCaffrey workload, Chase targets, Kelce red-zone usage |
| `team` | Bills pace and scoring |
| `matchup` | Week 12 RB defensive matchups |
| `injury` | Week 15 practice reports |
| `league` | PPR scoring, passing leaders |
