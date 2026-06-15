# VeriDoc — Product Requirements Document (v1)

> **Status:** Planning complete. Next milestone: **M0 — Walking skeleton.**
> **Scope of this PRD:** v1 only. The full 6-month vision lives in `PROJECT_SPEC.md`; this
> document re-scopes it into a buildable, eval-first v1.

---

## 1. Overview

**VeriDoc** is an agentic, VLM-native document-intelligence system. You upload a messy
real-world document (an invoice, a bank statement) and get back structured, schema-valid
data where **every field carries a calibrated confidence and a clickable link to its exact
source location** — and the system **abstains** on low-confidence fields instead of
hallucinating.

**The thesis is trust, not extraction.** Any VLM can return JSON. VeriDoc's differentiator
is the trust layer:

- **Source-grounding** — every extracted value is checked against the pixels/text it came from.
- **Calibrated confidence** — a verifier re-scores each field; confidence numbers mean what they say (measured by ECE).
- **Abstention** — fields below threshold are not auto-accepted; they route to a human-review queue.

This is the exact capability the IDP market pays for: *"auto-process at 99% precision,
escalate the rest."*

---

## 2. Problem statement

Enterprises drown in semi-structured documents. Two failure modes:

- **Legacy OCR pipelines** break on multi-column layouts, handwriting, mixed-language
  (Hinglish) text, and changing templates.
- **Raw LLM/VLM extractors** fix accuracy but introduce a worse problem: **silent
  hallucination with no confidence signal.** Because no field can be trusted, humans must
  review *everything* — which destroys the ROI of automation.

The unmet need is not higher raw accuracy; it is **knowing which fields you can trust** so
the high-confidence majority can be automated and only the uncertain minority is reviewed.

---

## 3. Target users

- **BFSI ops teams** (loan origination, KYC, claims) — highest-volume, highest-pain vertical.
- **Indian fintech / lending startups** processing bank statements and invoices/GST data.
- **SMB accounting / procurement teams.**
- **Mid-market back-offices** that can't afford $18K/yr enterprise IDP seats.

v1 optimizes for the BFSI/lending wedge: **invoices + bank statements**.

---

## 4. Goals & non-goals (v1)

**Goals**
- Prove the trust loop end-to-end on two contrasting doc types.
- Produce honest, reproducible numbers: field-level F1, hallucination rate, calibration (ECE), and **% auto-processed at 99% precision**.
- Demonstrate eval maturity (regression CI gate) and production-awareness (guardrails, tracing, cost-per-doc).
- Stay within ≤ $5 total spend on free tiers.

**Non-goals (v1)** — see §12 for the full list.
- Not a multi-tenant SaaS; not a billing/auth product.
- Not chasing maximum doc-type coverage — two types, done well.
- Not fine-tuning the VLM extractor itself.

---

## 5. Scope

| In scope (v1) | Out of scope (v1) |
|---|---|
| **Invoices + bank statements** (only these two) | Any other doc type (GST filings, KYC, lab reports, shipping) |
| Multi-page ingest (PDF + image) | Real-time / streaming ingestion |
| VLM → schema extraction (Instructor/Pydantic) | Full **VLM** fine-tuning (Qwen2.5-VL) |
| Verifier + calibrated confidence | Active-learning / human-in-the-loop retraining loops |
| Abstention/escalation gate + review-queue **data model** | A polished review-queue *workflow* UI with assignment/SLA |
| Field-level eval suite + regression CI gate | Multi-annotator labeling platform |
| Langfuse tracing + cost-per-doc | Full alerting/on-call observability stack |
| MCP server exposing the extractor | Public MCP marketplace / auth |
| `pgvector` few-shot exemplar retrieval | Separate/managed vector DB |
| **Router (+optional verifier) fine-tune on Kaggle/Colab** | GPU-hosted inference; paid model tiers |
| Minimal result viewer → later Next.js + shadcn viewer | Mobile app; multi-language UI |
| docker-compose on-prem path | Production k8s / autoscaling infra |
| Free tiers only (Vercel, Render/Railway, Neon, Langfuse, Gemini) | Any non-free infrastructure |

---

## 6. Functional requirements

1. **Ingest** a document (PDF or image), including multi-page, and normalize to per-page images.
2. **Classify** the document type (invoice vs bank statement) via a router.
3. **Extract** fields into the typed schema for that doc type (§8).
4. **Verify** each extracted field against its source crop (the region it was read from).
5. **Score** a calibrated confidence ∈ [0, 1] per field.
6. **Abstain** on fields below the configured threshold (mark `status = abstained`).
7. **Queue** abstained/low-confidence fields and documents for human review (data model + API).
8. **Persist** jobs, results, per-field provenance, and an immutable audit log per document.
9. **Expose** extraction as an **MCP tool/server** callable from MCP-compatible clients.
10. **Retrieve** similar past documents from `pgvector` as few-shot exemplars for rare layouts.
11. **Display** results: minimal viewer in early milestones; bbox overlays + confidence chips + review queue in the Next.js viewer later.

---

## 7. Non-functional requirements

- **Cost:** ≤ $5 total; everything on free tiers. Realistic target $0–3.
- **Platform:** Windows + Python 3.11. Pinned dependency versions; no exotic/unmaintained libraries.
- **On-prem capable:** one-command `docker compose` path; runs offline (Ollama VLM) for DPDP/data-sovereignty story.
- **Observability:** every VLM call traced in Langfuse (tokens, latency); cost-per-doc and p95-latency tracked.
- **Reproducibility:** the eval harness is deterministic and runnable from a single command; the headline numbers regenerate from the labeled benchmark.
- **Incrementality:** every milestone is end-to-end and emits a visible output + a recorded number.

---

## 8. Field-level extraction schemas (the two v1 doc types)

Every field is wrapped so it carries provenance and a trust signal, not just a value:

```
Field {
  value:           <typed>            # string | number | date | null
  confidence:      float ∈ [0, 1]
  source_location: { page: int, bbox: [x0, y0, x1, y1] } | null
  status:          "extracted" | "abstained"
}
```

`status = abstained` ⇒ the value was not confidently grounded and is routed to review.
A field with `source_location = null` fails the source-grounding check and is auto-flagged.

### 8.1 Invoice

| Field | Type | Notes |
|---|---|---|
| `invoice_number` | string | |
| `invoice_date` | date | |
| `due_date` | date? | optional |
| `vendor_name` | string | |
| `vendor_gstin` | string? | India-specific, optional |
| `vendor_address` | string | |
| `buyer_name` | string | |
| `buyer_gstin` | string? | optional |
| `currency` | string | ISO code where present |
| `subtotal` | decimal | |
| `tax` | object? | `{ cgst?, sgst?, igst?, total_tax }` |
| `total_amount` | decimal | |
| `line_items` | list | each: `{ description, hsn_sac?, quantity, unit_price, line_total }` |

### 8.2 Bank statement (multi-page)

| Field | Type | Notes |
|---|---|---|
| `account_holder_name` | string | |
| `account_number` | string | **PII — masked** before persistence/display |
| `bank_name` | string | |
| `ifsc` | string? | India-specific, optional |
| `statement_period` | object | `{ start: date, end: date }` |
| `opening_balance` | decimal | |
| `closing_balance` | decimal | |
| `currency` | string | |
| `transactions` | list | spans pages; each: `{ date, narration, debit?, credit?, balance, ref_no? }` |

---

## 9. Success metrics — definition of "done"

The trust layer is only credible if measured. v1 is "done" when these are computed,
reproducible, and reported in `eval/REPORT.md`:

| Metric | Definition |
|---|---|
| **Field precision / recall / F1** | Per-field and macro-averaged, against the hand-labeled benchmark. |
| **Hallucination rate** | % of accepted field values **not grounded** in the source (value absent from its source crop/text). |
| **Calibration — ECE + reliability diagram** | Expected Calibration Error of the confidence scores; reliability curve plotted. |
| **% auto-processed at 99% precision** | The headline automation number: fraction of fields auto-accepted while holding ≥ 99% precision on the accepted set. |
| **Abstention / coverage rate** | % of fields abstained (the trade-off partner of the above). |
| **Cost per document** | From Langfuse token/latency traces. |
| **p95 latency** | Per document. |

**v1 targets (to refine after the M0 baseline — anchored to the "before" number):**
- Macro field-F1: set a concrete target above the M0 baseline.
- Hallucination rate on accepted fields: ≤ ~2%.
- ECE: ≤ ~0.05.
- ≥ a meaningful % of fields auto-processed at 99% precision (set after baseline; the story is *"reviewers touch X% of fields instead of 100%"*).

> Targets are deliberately stated relative to the M0 baseline rather than as absolute
> promises before any data exists. The baseline number is the contract.

---

## 10. Phased milestones (mapped to `PROJECT_SPEC.md` roadmap)

Each milestone is a small, end-to-end, verifiable slice with a **visible output + a number**.

- **M0 — Walking skeleton (Slice 0).** *(Spec: Month 1)*
  One invoice → naive Gemini Flash VLM→JSON (prompt-only, no schema enforcement) →
  minimal display → **baseline accuracy number** on ~10 hand-labeled invoices.
  **Output:** one invoice end-to-end + the "before" number.

- **M1 — Structured extraction + metrics.** *(Spec: Month 1–2)*
  Instructor/Pydantic schemas, bounded retries, source-grounding stub; field-F1 +
  hallucination metrics; add bank-statement ingestion + multi-page handling; wire Langfuse.
  Grow benchmark to ~50–100 docs.
  **Output:** both doc types → schema, with F1 + hallucination numbers.

- **M2 — Verifier + confidence (core IP).** *(Spec: Month 3)*
  Verifier node re-checks each field vs its source crop and assigns confidence;
  calibration (ECE + reliability diagram); abstention/escalation gate + review-queue
  data model. Benchmark to 300+.
  **Output:** calibrated confidence + first "% auto-processed at 99% precision" number.

- **M3 — Agentify + MCP + RAG + fine-tune.** *(Spec: Month 4)*
  Full LangGraph pipeline (Router→Extractor→Verifier→Gate→Aggregator); doc-type router;
  **fine-tune router (+ optional verifier) on Kaggle/Colab, record before/after lift**;
  `pgvector` few-shot retrieval; MCP server; regression CI gate in GitHub Actions.
  **Output:** agentic pipeline + MCP + fine-tuning lift number + CI gate.

- **M4 — Frontend + deploy + dashboards.** *(Spec: Month 5)*
  Next.js + shadcn viewer (bbox overlays, confidence chips, review queue, dashboard);
  deploy on free tiers; cost-per-doc + p95 dashboards; PII redaction; immutable audit log;
  docker-compose on-prem path.
  **Output:** live demo + dashboards.

- **M5 — Harden + write-up.** *(Spec: Month 6)*
  Load test, guardrail hardening, README numbers table + demo GIF, `eval/REPORT.md`,
  90-second demo.
  **Output:** portfolio-ready repo.

---

## 11. Risks & mitigations

| Risk | Mitigation |
|---|---|
| **Labeling is tedious** | Scope to two doc types; use synthetic generation to scale the benchmark; start with ~10 labels at M0. |
| **VLM cost / latency** | Model tiering (cheap-first, escalate on low confidence) + exemplar caching; track cost-per-doc from day one. Turn the constraint into a talking point. |
| **"Looks like a wrapper"** | Keep eval + calibration + verifier front and center — they are the product, not the VLM. |
| **Free-tier quotas / limits** | Gemini free tier as default; Ollama fallback for offline dev; batch and cache calls; the $5 buffer covers overflow judge calls. |
| **4GB VRAM can't run the VLM** | Hosted Gemini is the dev default; local Ollama path is the on-prem story, not the hot path. Fine-tuning runs on Kaggle/Colab T4, not locally. |

---

## 12. Explicit non-goals (v1)

- **No doc types beyond invoices + bank statements.**
- **No full VLM (Qwen2.5-VL) fine-tuning** — only the small router/verifier are fine-tuned (on Kaggle/Colab).
- **No scaled real-user onboarding** — that is a post-v1 (Month-6) activity in the spec.
- **No multi-tenant auth, billing, or SaaS surface.**
- **No mobile app.**
- **No paid infrastructure** — free tiers only; ≤ $5 total.
- **No production-grade review-queue workflow** (assignment, SLAs) — only the data model + minimal queue in v1.
