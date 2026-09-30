# DataPilot AI

**AI-powered data intelligence platform** — ask in plain English; DataPilot plans the
workflow, gathers data from permitted sources, cleans and validates it, analyzes it
deterministically, explains the results, and traces every insight back to its evidence.

[![Watch the demo](https://img.youtube.com/vi/GEZ5cZDK9N0/hqdefault.jpg)](https://www.youtube.com/shorts/GEZ5cZDK9N0)

▶ **[Watch the 60-second demo](https://www.youtube.com/shorts/GEZ5cZDK9N0)** — full pipeline: question → workflow → validation → dashboard → evidence.

```
ASK → UNDERSTAND → PLAN → SOURCE → COLLECT → PROCESS → VALIDATE → ANALYZE → VISUALIZE → EXPLAIN → EVIDENCE
```

## The key design decision: our own AI engine

The orchestration intelligence — intent extraction, dynamic workflow planning, tool
selection, insight generation — is a **deterministic engine built from scratch** in
Python. There is no dependency on an LLM for anything that produces a number.

| Layer | What it does | Implementation |
|---|---|---|
| Intent (`agents/intent.py`) | NL → structured intent (topic, region, period, dimensions, metrics, analyses) + clarifying questions | Own regex/heuristic NLU; optional OpenAI refinement |
| Planner (`agents/planner.py`) | Intent → dynamic step graph (a relationship query adds normalize+join; an anomaly query adds anomaly detection) | Own composition engine |
| Tool layer (`agents/tools.py`) | The ONLY capabilities the orchestrator can invoke (search_sources, collect, clean, validate, join, analyze, chart, evidence) | Controlled tools, each auditable |
| Analysis (`engines/analysis.py`) | Totals, growth, trend, correlation (association ≠ causation), anomalies | NumPy/Pandas — deterministic |
| Insight (`agents/insight.py`) | Phrases computed results; refuses causal claims; reports insufficient data honestly | Own template engine; optional OpenAI polish (numbers untouched) |

Optional `OPENAI_API_KEY` only *enhances phrasing*; the product runs 100% offline without it.

## Stack

- **Frontend:** React 19 + TypeScript + Vite, Tailwind v4, Recharts, React Flow (xyflow), Lucide
- **Backend:** FastAPI + Pydantic v2 + SQLAlchemy 2, Pandas/NumPy, SSE (sse-starlette)
- **DB:** SQLite by default, PostgreSQL via `DATABASE_URL` (docker-compose included)
- **Assets:** Cloudinary signed uploads (asset + evidence layer) with local-mode fallback

## Quickstart (no keys needed)

```bash
# 1. Backend
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8000   # http://localhost:8000/health

# 2. Frontend (new terminal)
cd frontend
npm install
npm run dev                                   # http://localhost:5173
```

The database seeds itself on boot: permitted source registry, default project, and two
demo datasets (with deliberately planted dirty rows so validation visibly catches
duplicates, negatives, unit-mismatch strings, and entity variants).

## The 60-second demo script

1. **Home** → click *"Compare rainfall and wheat production across Haryana districts from 2020 to 2025."*
2. Watch the **live workflow**: Understand → Sources → Collect → Process → Validate (97.6%, 1 invalid caught) → Analyze → Visualize → Insights → Evidence — mirrored on the **React Flow graph**.
3. Dashboard opens: KPIs (Avg Rainfall, Total Production, **Correlation r = +0.96**, Data Quality), production/rainfall trends, **scatter of rainfall vs production per district**.
4. Insight: *"strong positive association"* — click **Explain Result** → the exact calculation.
5. Click **View Evidence** → the full chain: calculation → 5 transformations (duplicate removal, type conversion, unit-mismatch quarantine, invalid exclusion) → validation metrics → dataset → asset → licensed source.
6. Run the EV query: **+227% growth, fastest-growing manufacturer ranked by bar chart.**
7. **Datasets** page: schema inference + quality scores; upload any CSV (direct-to-Cloudinary when keys are set).
8. **History** reopens any past dashboard/evidence; **Permitted Sources** shows the registry the AI is restricted to.

## Judge Q&A (built-in, not just claimed)

- **"Isn't this just ChatGPT?"** — The LLM is optional. The planner is a composition engine; every number comes from `engines/` with an exact calculation string you can read in the Evidence page.
- **"How do you prevent hallucinations?"** — The LLM never produces numbers. It may rephrase. Validation reports quality; analysis excludes flagged values; insights are generated from computed results.
- **"What if data is bad?"** — Validation catches duplicates/invalids/schema issues and the workflow *reports* them; the evidence trail shows exactly what was cleaned.
- **"Where is the AI?"** — Intent extraction, dynamic planning, orchestration, and explanation — all implemented and inspectable in `backend/app/agents/`.
- **"Why Cloudinary?"** — Asset + evidence layer: datasets and their provenance chain point back to the managed asset (`cloudinary_public_id` on every dataset; demo assets upload automatically when keys are present).

## Tests

```bash
cd backend && python -m pytest tests/ -q     # 19 tests: engines, intent, planner
cd frontend && npm run build                 # typecheck + production build
python scripts/e2e_check.py                  # live end-to-end (server running)
```

## Deployment

```bash
cp .env.example .env    # add Cloudinary/OpenAI keys if you have them
docker compose up --build
# frontend on :8080, API on :8000 (PostgreSQL included)
```

## Repository layout

```
backend/
  app/
    agents/     orchestrator.py intent.py planner.py tools.py insight.py
    engines/    processing.py validation.py analysis.py visualization.py
    services/   cloudinary.py source_registry.py events.py
    api/        queries.py workflows.py datasets.py projects.py
    seed/       bootstrap.py demo_data.py
  tests/        19 pytest cases
  scripts/      e2e_check.py
frontend/
  src/
    pages/      Home WorkflowLive Dashboard Datasets Evidence History
    components/ WorkflowGraph StepList ChartRenderer InsightCard
    api/ state/ types/
docker-compose.yml  .env.example
```

## Deferred (post-hackathon)

Multi-user auth, schema-drift alerts, forecasting, map visuals, live API connectors
(currently bundled snapshots through the same tool interface).
