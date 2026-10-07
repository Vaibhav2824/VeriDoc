# VeriDoc — Completion Plan (M4 finish + M5)

Goal: finish M4/M5, host the frontend on **GitHub Pages**, move the database to **Supabase**,
and rebuild the UI with shadcn/ui + animated component registries + GSAP.

Resume rule: work top to bottom, tick boxes as you go, commit after each phase.
Branch: `feat/pages-supabase-ui`.

## Architecture (target)

```
GitHub Pages (static Next.js export, /VeriDoc basePath)
        │  fetch  (NEXT_PUBLIC_API_URL, baked at build time)
        ▼
Render free web service (FastAPI + LangGraph pipeline, Groq/Gemini keys stay server-side)
        │  SQLAlchemy / psycopg3
        ▼
Supabase Postgres (+ pgvector): extraction_jobs, audit_events, exemplars — RLS on, no anon access
```

GitHub Pages only serves static files, so the Python pipeline and the API keys **cannot** live there.
The API runs on Render (already has `render.yaml`). Supabase is reached only by the API through
`DATABASE_URL`. No supabase-js in the browser: one data path, and the anon key never touches PII.

Not used: **Webflow** is a separate hosted site builder that doesn't fit Pages + Next.js.
**SkeuDesign** is a design-asset store, not a code dependency. If you want either, say so.

## Phase 0 — Prep
- [x] Clone/inspect, write this plan
- [x] Branch `feat/pages-supabase-ui`, commit pending `web/.gitkeep` deletion

## Phase 1 — Supabase database
- [x] `init_schema()` in `services/api/db.py` + `services/api/rag/store.py`: `ENABLE ROW LEVEL SECURITY`
      on every table (Supabase exposes `public` through PostgREST; with RLS on and no policies, anon/authenticated get nothing, and the `postgres` role the API uses bypasses RLS)
- [x] `.env.example`: Supabase **session pooler** URL (IPv4, port 5432) replaces Neon; docs in README
- [x] Unit test: RLS statement emitted for each table (no live DB in CI)
- [ ] **You:** create Supabase project → Settings → Database → copy session-pooler URI into local `.env` + Render env
- [ ] Run `init_schema()` once against Supabase and re-seed exemplars

## Phase 2 — API ready for public hosting (Render)
- [x] Move `scikit-learn` from dev deps to runtime deps (router artifact needs it; Render runs `uv sync --no-dev`)
- [x] CORS: `ALLOWED_ORIGINS` env (default `http://localhost:3000`), set to `https://vaibhav2824.github.io` on Render
- [x] Upload guard: reject files > 10 MB (413) — trust boundary
- [x] `resolve` endpoint: 404 when job/field missing (frontend currently ignores errors)
- [x] `render.yaml`: add `ALLOWED_ORIGINS`, `PYTHON_VERSION`
- [x] Tests for size limit + CORS env parsing
- [ ] **You:** Render → New → Blueprint → this repo; paste secrets (GROQ/GEMINI/DATABASE_URL/LANGFUSE)
- [x] `keepalive.yml` cron pings `/health` every 14 min (Render free sleeps after 15; 744 h/mo fits the 750 h free quota)

## Phase 3 — Static frontend on GitHub Pages
- [x] `next.config.ts`: `output: "export"`, `basePath`/`assetPrefix` from `NEXT_PUBLIC_BASE_PATH`, `images.unoptimized`, `trailingSlash`
- [x] `jobs/[id]` → `jobs/?id=` (dynamic routes can't be statically exported for unknown IDs)
- [x] `web/Dockerfile` → nginx serving `out/` (keeps the docker-compose on-prem path working)
- [x] Delete `vercel.json` (replaced by Pages)
- [x] `.github/workflows/pages.yml`: build `web/` with `vars.API_URL` → `NEXT_PUBLIC_API_URL` → `actions/deploy-pages`
- [x] CI: add `npm ci && npm run lint && npm run build` job for `web/`
- [ ] **You:** repo Settings → Pages → Source: GitHub Actions; Settings → Variables → `API_URL=<render url>` (used by Pages build + keepalive)

## Phase 4 — UI overhaul
Stack: shadcn/ui (`components.json` already set, base-nova), Tailwind v4, lucide, `motion`, GSAP (+ScrollTrigger),
animated components pulled from Smooth UI / Skiper UI / Unlumen UI shadcn registries via `npx shadcn add <url>`.
Concept: "trust you can see" — every field shows its confidence and where it came from.

- [x] shadcn base: button, card, badge, table, tabs, progress, tooltip, skeleton, dialog, input, sonner, chart, separator
- [x] App shell: top nav (Extract / Review queue / Dashboard / Eval), theme toggle (dark default), API status pill (handles Render cold start: "waking API…")
- [x] Landing `/`: GSAP hero — a document "scan" animation where fields light up with confidence chips; headline numbers from `eval/REPORT.md` (animated counters); how-it-works pipeline (Router→Extractor→Verifier→Gate) with ScrollTrigger; upload dropzone
- [x] Job viewer `/jobs/?id=`: progress states while polling; doc preview with **bbox overlays** from `source_location` (preview kept in-browser only — never persisted, PII rule); field table with confidence chips (green ≥0.9 / amber ≥ threshold / red abstained), ungrounded flag, raw JSON tab
- [x] Review queue `/queue`: table with inline correction, optimistic resolve + toast, empty state
- [x] Dashboard `/dashboard`: KPI tiles (jobs, p95 latency, pending review, auto-processed %), charts (by status, by doc type)
- [x] ~~Eval page~~ folded into the landing metrics section (YAGNI)
- [x] Respect `prefers-reduced-motion` (GSAP + motion), keyboard focus, contrast in both themes; check at 375 px

Extra fixes found while building:
- [x] Bboxes came back on Gemini's 0-1000 grid, not [0,1] as documented: normalized in `SourceLocation`
- [x] Bank statements have no verifier yet: UI shows their values as "unverified" instead of hiding them
- [x] shadcn CLI installed an unrelated npm package `cn`: removed, `lib/utils.ts` added

## Phase 5 — Harden + write-up
- [ ] `uv run ruff check . && uv run mypy . && uv run pytest` green; `npm run build` green
- [ ] Code review pass (correctness + security) on the diff
- [x] README: live demo link, architecture diagram, numbers table, setup (Supabase/Render/Pages), demo GIF
- [ ] CLAUDE.md status → M4 done; `graphify update .`
- [ ] Open PR, merge, confirm Pages deploy is live

## Needs from you (can't be done by Claude: account creation + secrets)
1. Supabase project + session-pooler connection string
2. Render account, Blueprint deploy, secrets pasted in Render dashboard
3. GitHub: Pages source = Actions, repo variable `API_URL`
