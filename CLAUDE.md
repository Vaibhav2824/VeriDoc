# VeriDoc — Operating Guide

Agentic, VLM-native document intelligence whose differentiator is **trust**: every
extracted field carries a calibrated confidence + a source link, and the system **abstains**
on low-confidence fields instead of hallucinating. See `PRD.md` for scope, `PROJECT_SPEC.md`
for the full vision.

**Status:** M0 complete. Walking skeleton + eval harness committed (commit `2a39ef3`).
Next: **M1 — Structured extraction** (Instructor/Pydantic invoice schema, bounded retries, Langfuse tracing, bank-statement ingestion).
Baseline: run `uv run python -m eval.run` after labeling ~10 Kaggle invoices to record the M0 number.

## Environment & constraints (fixed)

- **OS / runtime:** Windows, Python 3.11. PowerShell shell.
- **Local hardware:** 16GB RAM, 4GB VRAM GPU. Anything heavier than a small local model runs on a free hosted tier — **never locally**. The VLM does not run locally; Gemini Flash (hosted) is the default.
- **Budget:** ≤ $5 total, all free tiers (Vercel, Render/Railway, Neon Postgres+pgvector, Langfuse, Gemini free tier). Ollama is for local/offline on-prem dev only.
- **Training compute:** router/verifier fine-tunes run on **Kaggle / Colab free GPUs (T4)**, off-machine; artifacts are exported and pulled in. No GPU training locally.
- **Dependencies:** pinned versions; no exotic or unmaintained libraries.
- **Working style:** incremental, verifiable milestones with a visible output + a recorded number. Never a big-bang build.

## Tech stack (pin exact patch versions in the lockfile at install time)

**Backend (Python 3.11):**
- `fastapi` + `uvicorn` — API + async job handling
- `pydantic` v2 — schemas are the single source of truth
- `instructor` — structured VLM output against Pydantic models
- `langgraph` — agent orchestration (Router→Extractor→Verifier→Gate→Aggregator)
- `google-genai` — Gemini 2.x Flash SDK (default VLM)
- `ollama` client — on-prem VLM adapter (Qwen2.5-VL), not the hot path
- `langfuse` — tracing, token/latency, cost-per-doc
- `sqlalchemy` + `psycopg` + `pgvector` — Neon Postgres + few-shot exemplar retrieval
- `pytest`, `ruff`, `mypy` — test, lint, typecheck
- `uv` — environment + lockfile

**Frontend (deferred until after the eval loop + verifier exist):**
- `next` 15, `shadcn/ui`, Node 20

**Infra:** `docker-compose` (on-prem path), GitHub Actions (CI + eval regression gate).

> Versions above are target majors/SDKs. Exact patch versions are locked in `uv.lock` at
> install time — pin them, do not float.

## Repo structure (pragmatic modular — grows into the spec's monorepo later)

```
services/api/            # FastAPI app + LangGraph nodes (internal modules, not separate packages yet)
  models/                # Pydantic schemas: invoice, bank statement, Field wrapper
  nodes/                 # router, extractor, verifier, gate, aggregator
  clients/               # VLMClient interface + Gemini / Ollama adapters
eval/                    # benchmark docs, labels, metrics, regression harness
  REPORT.md              # the calibration + accuracy report (recruiters read this)
training/                # Kaggle/Colab fine-tune scripts + exported router/verifier artifacts
web/                     # Next.js + shadcn viewer (deferred)
infra/                   # docker-compose, deploy configs
notebooks/               # calibration plots, error analysis
PRD.md  PROJECT_SPEC.md  README.md  CLAUDE.md
```

## Coding conventions

- Type hints everywhere; `mypy` clean.
- **Pydantic models are the single source of truth** for every schema — never hand-roll dict shapes.
- Async I/O for all VLM/network calls.
- Metrics are **pure functions** (deterministic, unit-tested, no I/O).
- LangGraph control flow is **deterministic** with bounded retries + timeouts.
- No bare `except`; structured logging routed to Langfuse.
- Keep modules small and single-purpose; match surrounding style.

## Commands (placeholders now; fill in as code lands)

| Purpose | Command |
|---|---|
| Setup env | `uv sync` |
| Extract invoice (M0 CLI) | `uv run python scripts/extract_invoice.py <path>` |
| Run API | `uv run uvicorn services.api.main:app --reload` *(placeholder — M1)* |
| Tests | `uv run pytest` |
| Lint | `uv run ruff check .` |
| Typecheck | `uv run mypy .` |
| Eval harness | `uv run python -m eval.run` |
| Regression gate | `uv run python -m eval.regression` |

## Eval-first workflow

- **Never merge without a number.** Every change re-runs the eval harness.
- The M0 **baseline** is the contract; later milestones are measured against it.
- The **regression CI gate** (GitHub Actions) fails a PR if macro field-F1 drops beyond the configured threshold.
- Headline numbers (F1, hallucination rate, ECE, % auto-processed at 99% precision) live in `eval/REPORT.md` and regenerate from the labeled benchmark.

## Guardrails (enforce these — they are the product)

- **Schema enforcement:** all extraction goes through Instructor/Pydantic. Invalid output → bounded retry → then **abstain**. Never emit an unvalidated field.
- **Confidence-threshold abstention:** fields below the threshold are *not* auto-accepted; they are marked `status = abstained` and routed to the review queue.
- **Source-grounding check:** a field value with no support in its source crop/text is auto-flagged and counts toward the hallucination metric. `source_location = null` ⇒ flagged.
- **Bounded retries:** every node has a max-retry count + timeout. **No retry-loop blowup** — track the retry/cost budget and fail closed.
- **PII:** detect + redact (account numbers, etc.) **before** persistence and display.

## Model interface & tiering

- A single `VLMClient` interface; `GeminiClient` (default) and `OllamaClient` (on-prem) implement it.
- **Tiering:** cheap model first, escalate to a stronger model only on low confidence — the cost-optimization story. Track cost-per-doc to prove it.
- Fine-tuned **router/verifier** artifacts (trained on Kaggle/Colab) load locally; a small fine-tuned router fits in 4GB via Ollama. The **VLM extractor is never fine-tuned** in v1.

## Per-feature Definition of Done

A feature is done only when **all** of these hold:
1. Pydantic schema defined (if it touches data).
2. Unit tests pass (`pytest`), `ruff` + `mypy` clean.
3. Eval metric wired into the harness (if it affects extraction/trust).
4. Langfuse trace emitted for any VLM call.
5. Relevant guardrail enforced (schema / abstention / grounding / retries / PII).
6. Number recorded in `eval/REPORT.md`.
7. `graphify update .` run to keep the knowledge graph current.

---

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
