# PROJECT — Agentic, VLM-native Document Intelligence with a calibrated confidence + verification layer

**Working name:** `VeriDoc` (rebrand freely)
**One-liner:** Upload any messy real-world document; get structured, schema-valid data back, where every field carries a calibrated confidence and a clickable link to its exact source location — and the system *abstains* on low-confidence fields instead of hallucinating.

### Score (1–10)

| Criterion | Score |
|---|---|
| Resume impact | 9 |
| Recruiter interest | 10 |
| AI/ML depth | 8 |
| Software engineering depth | 9 |
| Deployment difficulty | 8 |
| Uniqueness | 8 |
| Startup potential | 9 |
| Research potential | 7 |
| Standing out vs. 1000 candidates | 8 |
| Helping secure a high-paying job | 9 |

### Executive summary

A production-grade Intelligent Document Processing system built VLM-first (the document is treated as a single visual-semantic object, not OCR-then-parse). The differentiator is not extraction — it's **trust**: a verifier agent re-checks every extracted field against the source crop, assigns a calibrated confidence, and routes anything below a threshold to a human-review queue. You ship it with a hand-labeled benchmark, a field-level accuracy + hallucination-rate metric, calibration (ECE) numbers, a regression CI, full tracing, and a cost-per-document dashboard.

### Why this beats other ideas

Most student IDP projects stop at "VLM returns JSON." That's a demo, not a product, because enterprises can't deploy a system that's confidently wrong 8% of the time with no way to know which 8%. The entire value of modern IDP has moved from raw accuracy to *threshold-based automation* — "auto-process at 99% precision, escalate the rest." Building that calibration + verification + abstention loop is the exact thing the market pays for and the exact thing that demonstrates eval maturity. It's also objectively measurable, which gives you clean resume numbers and clean interview stories.

### Problem statement

Enterprises drown in semi-structured documents (invoices, GST filings, bank statements, KYC packets, lab reports, shipping docs). Legacy OCR pipelines break on multi-column layouts, handwriting, mixed-language (Hinglish) text, and changing templates. LLM/VLM extractors fix accuracy but introduce a worse problem: silent hallucination with no confidence signal, so humans must review everything anyway — killing the ROI.

### Target users

- BFSI ops teams (loan origination, KYC, claims) — highest-volume, highest-pain vertical.
- Fintech / lending startups in India processing bank statements and GST data.
- SMB accounting/procurement teams.
- Mid-market back-offices that can't afford $18K/yr enterprise IDP seats.

### Market need

IDP is a ~$14B (2026) → ~$91B (2034) market, India is the fastest-growing region, and the explicit 2026 procurement criteria are: VLM-native architecture, field-level confidence scoring, on-prem/data-sovereignty support, and workflow integration. Your project hits four of four.

### Complete system architecture

- **Frontend:** Next.js + shadcn/ui on Vercel (free). Document viewer with bounding-box overlays, per-field confidence chips, a "needs review" queue, and an accuracy/cost dashboard. (Polish matters: recruiters judge the 30-second demo.)
- **Backend:** FastAPI on Render or Railway free tier (or HF Spaces). Async job queue for multi-page docs.
- **Databases:** Postgres on Neon (free) for jobs/results/audit log; `pgvector` on the same instance for few-shot example retrieval (no separate vector DB needed — a cost-awareness talking point).
- **AI models:** VLM-native extraction. Default to an open VLM (Qwen2.5-VL 3B/7B) run locally via Ollama, with Gemini 2.x Flash free tier as a higher-accuracy fallback/baseline. (Showing you can swap a self-hosted open model for a hosted one is the on-prem story.)
- **Agent framework:** LangGraph. Pipeline: `Router (classify doc type) → Extractor (VLM → schema) → Verifier (re-check each field vs. source crop, score confidence) → Abstention/Escalation gate → Aggregator`.
- **MCP:** Expose the extractor as an MCP tool/server so the system is callable from MCP-compatible clients. This is a named 2026 hiring skill and very few students show it.
- **Vector DB:** `pgvector` for retrieving similar past documents as few-shot exemplars (improves accuracy on rare layouts).
- **Evaluation framework:** A 300–500 doc labeled benchmark (public + synthetic). Metrics: field-level precision/recall/F1, **hallucination rate**, **calibration (ECE / reliability diagram)**, and *% auto-processed at 99% precision*. LLM-as-judge for free-text fields, calibrated against ~100 human labels. Regression harness runs in GitHub Actions on every commit.
- **Monitoring/observability:** Langfuse (free) for full trace capture (every VLM call, token count, latency), plus a cost-per-document and p95-latency dashboard.
- **CI/CD:** GitHub Actions — lint, unit tests, and the eval regression gate (PR fails if field-F1 drops > X%). This single feature outperforms most students' entire repos as a signal.
- **Cloud:** Vercel + Render/Railway + Neon, all free tier. Optional Cloudflare R2 (free) for document storage.

### AI components (specifics)

- **Open-source models:** Qwen2.5-VL (extraction), a small text model for the verifier/router (can be Project 2's fine-tuned model — see integration).
- **Fine-tuning requirement:** Optional but high-value — fine-tune the *router/classifier* and optionally the *verifier* on your labeled set. Lets you cite a measurable accuracy lift from fine-tuning.
- **Agent architecture:** Supervisor + specialist nodes in LangGraph; deterministic control flow with bounded retries and timeouts (cite the "no retry-loop blowup" guardrail explicitly — that's a known production failure mode recruiters probe).
- **RAG architecture:** Retrieval of similar exemplar documents from `pgvector` to ground extraction on rare layouts (few-shot).
- **Evaluation methods:** Ground-truth field matching, hallucination detection (does the value exist in the source?), calibration, LLM-judge calibrated to humans, regression CI.
- **Guardrails:** Pydantic/Instructor schema enforcement, PII detection + redaction, confidence-threshold abstention, source-grounding check (a field with no source support is auto-flagged).
- **Observability:** Langfuse traces + cost/latency dashboards + an immutable audit log per document (compliance-grade, a selling point for BFSI).

### Tech stack

`Next.js`, `shadcn/ui`, `FastAPI`, `LangGraph`, `Qwen2.5-VL` (Ollama), `Gemini Flash` (free tier), `Instructor`/`Pydantic`, `Postgres + pgvector` (Neon), `Langfuse`, `GitHub Actions`, `MCP`, `Vercel` + `Render`.

### Development roadmap

- **Month 1 — Foundations & baseline.** Pick 2–3 doc types (e.g., invoices/GST + bank statements). Build the ingestion + viewer. Stand up a naive VLM→JSON extractor. Assemble a 100-doc seed benchmark with hand labels. Get a *baseline number* (this is your "before").
- **Month 2 — Schema + structured extraction.** Instructor/Pydantic schemas, retry logic, multi-page handling. Grow benchmark to 300+ docs. Add field-level F1 + hallucination-rate metrics. Wire Langfuse.
- **Month 3 — The verifier + confidence (the core IP).** Build the verifier agent that re-checks each field against its source crop and assigns confidence. Calibrate (ECE, reliability diagram). Implement the abstention/escalation gate and the human-review queue.
- **Month 4 — Agentify + MCP + RAG.** LangGraph orchestration, doc-type router (optionally fine-tuned), `pgvector` few-shot retrieval, MCP server. Add the regression CI gate.
- **Month 5 — Deploy + harden + dashboards.** Full deploy on free tiers. Cost-per-doc and p95 dashboards. Load test. Guardrails + audit log. PII redaction.
- **Month 6 — Real users + write-up.** Onboard 5–15 real users (a local CA/accountant, a campus club's paperwork, a small lender). Collect real usage + accuracy numbers. Write the README, a technical blog post, and record a 90-second demo. Optionally draft a short eval-methodology paper.

### Deployment plan

Vercel (frontend), Render/Railway (FastAPI), Neon (Postgres+pgvector), Ollama-served VLM locally for dev + Gemini free tier in prod, Langfuse cloud free tier. One-command `docker compose` for the on-prem story ("runs fully offline for DPDP compliance").

### Cost estimate (≤ $5)

Everything sits on free tiers. The $5 buffer covers occasional Gemini/Claude judge calls beyond free limits, or a cheap domain. Realistic spend: **$0–3**.

### Scalability strategy

Async worker queue, batched VLM calls, exemplar caching, model tiering (cheap open model first, escalate to a stronger model only on low confidence — a concrete cost-optimization story). Horizontal scale via stateless workers.

### Recruiter talking points

- "I built VLM-native extraction with a calibrated confidence layer; we auto-process at 99% precision and escalate the rest — so reviewers touch 22% of fields instead of 100%."
- "Hallucination rate dropped from X% to Y% after adding source-grounded verification."
- "Cost is $0.0N per document; here's the model-tiering that got it there."
- "Regression CI gates every PR on field-level F1."
- "It's exposed over MCP and runs fully offline for data-sovereignty."

### GitHub structure

```
veridoc/
  apps/web/            # Next.js frontend
  services/api/        # FastAPI + LangGraph
  packages/extractor/  # VLM extraction + schemas
  packages/verifier/   # confidence + abstention logic
  packages/mcp/        # MCP server
  eval/                # benchmark, labels, metrics, regression harness
  eval/REPORT.md       # the calibration + accuracy report (recruiters read this)
  infra/               # docker-compose, deploy configs
  notebooks/           # error analysis, calibration plots
  README.md            # architecture diagram, numbers, demo GIF
```

### Portfolio demonstration strategy

Lead the README with a numbers table and a demo GIF showing a messy invoice → structured fields with confidence chips → one low-confidence field flagged for review. Link the live demo, the Langfuse public dashboard (if shareable), and `eval/REPORT.md`. The 90-second video is your highest-leverage asset.

### Interview questions recruiters may ask

- How did you build your ground-truth set, and how do you handle labeler disagreement?
- How is confidence calibrated, and how do you measure calibration?
- What's your hallucination definition and how do you detect it automatically?
- Why VLM-native over OCR + LLM? Where does each fail?
- How do you prevent agent retry loops / runaway cost?
- What's your cost per document and how would you halve it?
- How would you run this fully on-prem for a bank?

### Research paper opportunities

- "Calibrated abstention for VLM document extraction" — confidence calibration + selective prediction on IDP. Workshop-tier viable.
- A benchmark contribution: a labeled Indic/Hinglish document extraction set (genuinely scarce; high citation potential).

### Startup opportunities

A vertical IDP for Indian BFSI/lending (bank-statement + GST analysis with confidence-gated automation) is a fundable wedge. On-prem/DPDP compliance is a real differentiator against US incumbents.

### Risks and challenges

- Labeling is tedious — scope to 2–3 doc types, use synthetic generation to scale.
- VLM cost/latency — mitigate with model tiering and caching (turn the risk into a talking point).
- "Looks like a wrapper" — defeated entirely by the eval + calibration + verifier layer. Keep that front and center.

### Expected learning outcomes

VLM application engineering, agent orchestration + guardrails, eval/calibration methodology, MCP, observability, cost optimization, full-stack deploy, on-prem packaging.