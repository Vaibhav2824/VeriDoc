# VeriDoc

Document extraction that shows its work. VeriDoc reads invoices and bank statements with a
vision-language model, and every field it returns carries a **calibrated confidence** and the
**box on the page it was read from**. Fields it isn't sure about are withheld and sent to a
human review queue instead of being guessed.

**Live demo:** https://vaibhav2824.github.io/VeriDoc/ (the sample invoice works even while the
free API instance is asleep)

## Results

Measured on the labeled benchmark in [`eval/`](eval/REPORT.md):

| Metric | Value |
|---|---|
| Macro field accuracy (after abstention gate) | **98.3%** |
| Fields auto-processed at 99% precision | **84.3%** |
| Expected calibration error | **0.0115** |
| Hallucination rate (value with no source) | **0.0%** |
| Router accuracy (130 docs) | **100%**, 0 tokens, <1 ms |

Trust metrics are on 29 labeled documents; routing on 130. See [`eval/REPORT.md`](eval/REPORT.md)
for method and per-field numbers.

## How it works

```
upload ──► Router ──► Extractor ──► Verifier ──► Gate ──► result + review queue
          TF-IDF+LR    Gemini Flash   re-checks each    conf < 0.80
          (fine-tuned) + Pydantic     field, adds       → withheld
                       schema         confidence + bbox
```

- **Router**: TF-IDF + logistic regression trained on 130 labeled docs (`training/`).
- **Extractor**: Gemini Flash (or Groq) through Instructor into strict Pydantic schemas, with
  bounded retries and pgvector few-shot exemplars.
- **Verifier**: second pass that scores each field and locates it on the page.
- **Gate**: fields under `CONFIDENCE_THRESHOLD` are abstained and queued for review.
- **Guardrails**: PII masking before persistence, immutable audit log, bounded retries.

## Architecture

| Piece | Where it runs | Code |
|---|---|---|
| Web UI (Next.js static export, shadcn/ui, GSAP) | GitHub Pages | [`web/`](web) |
| API + LangGraph pipeline (FastAPI) | Render free tier | [`services/api/`](services/api) |
| Postgres + pgvector (jobs, audit log, exemplars) | Supabase | [`services/api/db.py`](services/api/db.py) |
| MCP server | local | [`services/mcp/`](services/mcp) |

The browser only talks to the API. Supabase is reached by the API alone, and every table has
row-level security enabled with no policies, so the public Supabase REST endpoint exposes nothing.

## Deploy your own (all free tiers)

1. **Supabase**: create a project, then *Connect → Session pooler* and copy the URI.
   Tables are created on first API start.
2. **Render**: *New → Blueprint* and pick this repo (`render.yaml`). Set `GEMINI_API_KEY`
   (and optionally `GROQ_API_KEY`), `DATABASE_URL` (the Supabase URI), and the Langfuse keys.
   `ALLOWED_ORIGINS` defaults to `https://vaibhav2824.github.io`; change it for your fork.
3. **GitHub**: *Settings → Pages → Source: GitHub Actions*, then
   *Settings → Secrets and variables → Actions → Variables* and add `API_URL` with your Render
   URL. Push to `main` and `.github/workflows/pages.yml` publishes the site.
   `keepalive.yml` pings the API every 14 minutes so the demo doesn't cold-start.

## Run locally

```bash
uv sync
cp .env.example .env   # add GEMINI_API_KEY; DATABASE_URL is optional (in-memory without it)
uv run uvicorn services.api.main:app --reload
```

```bash
cd web && npm ci && npm run dev   # http://localhost:3000
```

Offline / on-prem: `docker compose up` runs the API, the web UI (nginx) and Postgres + pgvector.

## Development

| Purpose | Command |
|---|---|
| Tests | `uv run pytest` |
| Lint / types | `uv run ruff check . && uv run mypy .` |
| Eval harness | `uv run python -m eval.run` |
| Regression gate | `uv run python -m eval.regression` |
| Extract one doc | `uv run python -m scripts.extract_document <path>` |
| Web lint / build | `cd web && npm run lint && npm run build` |

UI components come from [shadcn/ui](https://ui.shadcn.com) plus the
[SmoothUI](https://smoothui.dev), [Unlumen UI](https://ui.unlumen.com) and
[Skiper UI](https://skiper-ui.com) registries; the hero animation uses [GSAP](https://gsap.com).
