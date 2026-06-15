# Graph Report - .  (2026-06-15)

## Corpus Check
- Corpus is ~1,693 words - fits in a single context window. You may not need a graph.

## Summary
- 37 nodes · 45 edges · 6 communities
- Extraction: 87% EXTRACTED · 13% INFERRED · 0% AMBIGUOUS · INFERRED: 6 edges (avg confidence: 0.84)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_LangGraph Extraction Pipeline|LangGraph Extraction Pipeline]]
- [[_COMMUNITY_Model Tiering & Observability|Model Tiering & Observability]]
- [[_COMMUNITY_Evaluation & Calibration Suite|Evaluation & Calibration Suite]]
- [[_COMMUNITY_System Architecture & Stack|System Architecture & Stack]]
- [[_COMMUNITY_Confidence & Abstention Layer|Confidence & Abstention Layer]]
- [[_COMMUNITY_Guardrails & Schema Enforcement|Guardrails & Schema Enforcement]]

## God Nodes (most connected - your core abstractions)
1. `LangGraph Agent Framework` - 7 edges
2. `Extractor Node` - 7 edges
3. `VeriDoc System` - 5 edges
4. `Verifier Agent` - 5 edges
5. `Calibrated Confidence` - 5 edges
6. `Abstention / Escalation Gate` - 5 edges
7. `Evaluation Framework` - 5 edges
8. `Guardrails` - 4 edges
9. `Source-Grounding Check` - 3 edges
10. `Qwen2.5-VL` - 3 edges

## Surprising Connections (you probably didn't know these)
- `VeriDoc README` --references--> `VeriDoc System`  [INFERRED]
  README.md → PROJECT_SPEC.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **LangGraph Extraction Pipeline (Router to Aggregator)** — veridoc_project_spec_router, veridoc_project_spec_extractor, veridoc_project_spec_verifier_agent, veridoc_project_spec_abstention_gate, veridoc_project_spec_aggregator [EXTRACTED 1.00]
- **Trust Layer (Confidence + Verification + Abstention)** — veridoc_project_spec_calibrated_confidence, veridoc_project_spec_verifier_agent, veridoc_project_spec_abstention_gate, veridoc_project_spec_source_grounding [INFERRED 0.85]
- **Evaluation and Calibration Suite** — veridoc_project_spec_benchmark, veridoc_project_spec_hallucination_rate, veridoc_project_spec_calibration_ece, veridoc_project_spec_regression_ci [EXTRACTED 1.00]

## Communities (6 total, 0 thin omitted)

### Community 0 - "LangGraph Extraction Pipeline"
Cohesion: 0.28
Nodes (9): Aggregator Node, Extractor Node, LangGraph Agent Framework, MCP Server, pgvector Few-Shot RAG, Postgres on Neon, Bounded Retry / No Retry-Loop Blowup Guardrail, Router (Doc-Type Classifier) (+1 more)

### Community 1 - "Model Tiering & Observability"
Cohesion: 0.25
Nodes (8): Immutable Audit Log, Cost-per-Document Dashboard, Gemini 2.x Flash, Langfuse Observability, Model Tiering, Ollama, On-Prem / DPDP Compliance, Qwen2.5-VL

### Community 2 - "Evaluation & Calibration Suite"
Cohesion: 0.29
Nodes (7): Labeled Document Benchmark, Calibration (ECE / Reliability Diagram), Evaluation Framework, GitHub Actions CI/CD, Hallucination Rate Metric, LLM-as-Judge, Regression CI Gate

### Community 3 - "System Architecture & Stack"
Cohesion: 0.40
Nodes (5): FastAPI Backend, Next.js + shadcn/ui Frontend, VeriDoc System, VLM-native Extraction, VeriDoc README

### Community 4 - "Confidence & Abstention Layer"
Cohesion: 0.67
Nodes (4): Abstention / Escalation Gate, Calibrated Confidence, Human-Review Queue, Threshold-Based Automation

### Community 5 - "Guardrails & Schema Enforcement"
Cohesion: 0.50
Nodes (4): Guardrails, Instructor / Pydantic Schema Enforcement, PII Detection + Redaction, Source-Grounding Check

## Knowledge Gaps
- **12 isolated node(s):** `Human-Review Queue`, `Labeled Document Benchmark`, `LLM-as-Judge`, `Aggregator Node`, `MCP Server` (+7 more)
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Extractor Node` connect `LangGraph Extraction Pipeline` to `Model Tiering & Observability`, `Guardrails & Schema Enforcement`?**
  _High betweenness centrality (0.351) - this node is a cross-community bridge._
- **Why does `Verifier Agent` connect `LangGraph Extraction Pipeline` to `System Architecture & Stack`, `Confidence & Abstention Layer`, `Guardrails & Schema Enforcement`?**
  _High betweenness centrality (0.329) - this node is a cross-community bridge._
- **Why does `Calibrated Confidence` connect `Confidence & Abstention Layer` to `LangGraph Extraction Pipeline`, `Model Tiering & Observability`, `Evaluation & Calibration Suite`?**
  _High betweenness centrality (0.278) - this node is a cross-community bridge._
- **What connects `VLM-native Extraction`, `Human-Review Queue`, `Labeled Document Benchmark` to the rest of the system?**
  _14 weakly-connected nodes found - possible documentation gaps or missing edges._