<!--
SYNC IMPACT REPORT
==================
Version: 0.0.0 → 1.0.0 (MAJOR: Initial Constitution Ratification)
Ratified: 2026-04-17
Status: 9 Articles locked with 1 incomplete (Article IX truncated)

Modified/Added Principles:
  ✅ Article I — Language & Runtime (new)
  ✅ Article II — Agent Architecture (new)
  ✅ Article III — Human Accountability (new)
  ✅ Article IV — Data Layer (new)
  ✅ Article V — RAG & Grounding (new)
  ✅ Article VI — LLM Usage (new)
  ✅ Article VII — API & Frontend (new)
  ✅ Article VIII — Voice & File Handling (new)
  ⚠ Article IX — Over-Engineering Guard (INCOMPLETE)

Templates requiring updates:
  ⚠ plan-template.md (Constitution checks)
  ⚠ spec-template.md (Scope alignment)
  ⚠ tasks-template.md (Task categorization)

Follow-up TODOs:
  • Complete Article IX — Over-Engineering Guard (input was truncated at "Kafka/SQS/Rabbi")
  • Review plan-template.md for architecture constraints
  • Review spec-template.md for mandatory sections
  • Review tasks-template.md for principle-driven task types
-->

# Agentic Customer Support Flow Constitution

## Article I — Language & Runtime

**Backend is Python 3.11+ only** — no other backend languages permitted.

**Frontend is SvelteKit only** — no React, Vue, or other frameworks in v1.

**All Python dependencies pinned in requirements.txt** — floating versions introduce runtime divergence and must not appear in production environments.

**`from __future__ import annotations` required in all Python files** for forward-compatible type hint syntax.

*Rationale*: Locked runtime choices eliminate toolchain fragmentation, reduce onboarding friction, and ensure reproducible deployments across development and production.

---

## Article II — Agent Architecture

**All agentic flows implemented using LangGraph state machines only** — no other orchestration frameworks.

**Agent node names must use the `_node` suffix** to avoid collisions with FlowState keys (e.g., `triage_node`, `routing_node`).

**FlowState is the single shared contract between all agents** — no agent may pass data outside FlowState; all inter-agent communication is immutable and versioned.

**Node output must always be structured** (TypedDict / dict) — never freeform prose passed between nodes; each output must match a declared schema.

**Pipeline order is fixed**: Triage → Routing → RAG → Response → Supervisor.

**One bounded revision loop only** — no unbounded retry chains; maximum one revision pass, then escalate or send.

*Rationale*: Deterministic node contracts and fixed topology enable transparent audit trails, testability, and human oversight at every stage.

---

## Article III — Human Accountability

**The system is human-assist by design** — AI must never auto-send customer communications; every output requires explicit human approval or actionable delegation.

**Every pipeline output must route to a human review queue** — no draft is final without human sign-off.

**Supervisor agent must always produce a recommendation**: send / revise / escalate (one of three, always explicit).

**Escalation-trigger tickets must bypass drafting and route directly to senior human queue** — no further AI processing on escalations.

*Rationale*: AI removes administrative burden but humans remain accountable for customer-facing content and high-stakes decisions.

---

## Article IV — Data Layer

**Snowflake is the single source of truth** for all customer, order, and return data; no local copies or shadow systems.

**All Snowflake reads go through the FastAPI backend** — frontend never queries Snowflake directly.

**Cross-database queries use fully qualified 3-part names** (e.g., `db.schema.table`).

**SR_TICKET_NUMBER is VARCHAR** — all WHERE clauses must quote the value to prevent type coercion surprises.

**SR_RESOLUTION column must be VARCHAR(50) minimum** — never VARCHAR(10); resolution notes often exceed 10 characters and truncation causes data loss.

*Rationale*: Single-source-of-truth pattern prevents stale reads; quoted identifiers and sized fields eliminate silent failures.

---

## Article V — RAG & Grounding

**ChromaDB is the only vector store** — no other embedding databases in v1.

**Response agent must defer** ("I will confirm that policy") rather than hallucinate missing evidence.

**RAG citations must include**:
  - claim: the factual assertion made
  - source_doc: which document or knowledge base
  - source_section: which section/page
  - confidence score: 0.0 to 1.0

**Claims with confidence < 0.70 must be flagged by Supervisor as LOW_CONFIDENCE_CLAIM** and marked for human verification.

*Rationale*: Explainable grounding enables humans to audit reasoning and detect drift; low-confidence flags protect against customer-facing hallucinations.

---

## Article VI — LLM Usage

**LiteLLM with gpt-4o-mini is the only LLM provider in v1**.

**LiteLLM pinned to version 1.52.1** — do not upgrade without testing Windows cp1252 encoding edge cases.

**All LLM calls go through the agent layer** — no direct OpenAI calls from routes or frontend; all inference is auditable via LangGraph state.

**UTF-8 startup guard must remain in main.py** — ensures consistent encoding across Windows/Linux deployments.

*Rationale*: Single-provider choice simplifies testing and compliance; pinned version avoids runtime surprises; layered access enables monitoring and cost control.

---

## Article VII — API & Frontend

**FastAPI handles all backend routes** — no logic in SvelteKit server routes; server routes are thin adapters only.

**SvelteKit runs on port 5173, FastAPI on port 8000** — ports are fixed; no dynamic port allocation.

**SvelteKit reactive state uses local `$:` statements** — not derived stores after onMount; reactive declarations are co-located with component state.

**All API responses follow the existing router patterns in backend/app/routers/** — each new endpoint inherits the established request/response shapes.

*Rationale*: Clear separation of concerns keeps backend logic testable and frontend reactive without lifecycle complexity.

---

## Article VIII — Voice & File Handling

**OpenAI Whisper is the only transcription provider**.

**S3 upload failures are non-fatal** — treat as warnings, never block the ticket flow.

**Audio files use date-partitioned S3 keys** (e.g., `2026-04-17/ticket-12345-audio.webm`).

**Browser audio recording uses WebM format only**.

*Rationale*: Single transcription choice ensures consistent accuracy; non-blocking S3 failures prevent cascading outages; partitioned keys aid S3 lifecycle management.

---

## Article IX — Over-Engineering Guard

**No message queues (Kafka/SQS/RabbitMQ)** in v1.

TODO(ARTICLE_IX_COMPLETION): User input was truncated at "No message queues (Kafka/SQS/Rabbi". Please provide remaining rules for Article IX — Over-Engineering Guard (e.g., in-process queues, sync-first design, etc.).

*Rationale (partial)*: Synchronous, in-process architecture reduces operational complexity for a bounded, human-in-the-loop system.

---

## Governance

**This Constitution supersedes all other development practices and guidelines.** Compliance is non-negotiable; deviations require explicit amendment (see below).

**Amendment Procedure**:
  1. Proposed changes must cite the Article(s) and provide migration plan.
  2. Changes affecting agent topology or data contracts require architecture review.
  3. Amendments increment CONSTITUTION_VERSION per semantic versioning:
     - MAJOR: Principle removal or backward-incompatible redefinition (e.g., new required field in FlowState).
     - MINOR: New Article or materially expanded guidance (e.g., new agent type added to pipeline).
     - PATCH: Clarifications, wording, typo fixes (e.g., RESOLUTION size increased from 10 to 50).

**Compliance Review**:
  - All PRs must verify adherence to applicable Articles (use `/speckit-checklist` for per-feature validation).
  - Code review checklist must include: "Does this change align with Constitution?"
  - Violations discovered during review must be re-opened; approval is conditional on compliance.

**Guidance & Runtime**:
  - This Constitution sets governance; runtime development guidance lives in `.specify/memory/` (topic-specific files linked from MEMORY.md).
  - Template-specific checks are maintained in `.specify/templates/` and synced after each amendment.

---

**Version**: 1.0.0 | **Ratified**: 2026-04-17 | **Last Amended**: 2026-04-17
