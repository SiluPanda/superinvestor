# Superinvestor Epics and Issues Backlog

_Date: 2026-04-23_
_Source: `best-plan.md`_

This document translates the phased development plan into a practical epic-and-issue backlog that is ready to turn into GitHub milestones, epics, and implementation tickets.

---

## How to use this backlog

- Treat each **Epic** as a milestone-level outcome.
- Treat each **Issue** as a shippable unit of work.
- Keep the critical path focused on **trust → evals → point-in-time rigor → portfolio utility → paper deployment**.
- Do **not** pull Phase 6 or Phase 7 work forward unless earlier milestone gates are met.

### Suggested labels
- `phase:0` ... `phase:7`
- `type:epic`, `type:feature`, `type:infra`, `type:schema`, `type:ux`, `type:test`
- `area:agents`, `area:data`, `area:engine`, `area:store`, `area:tui`, `area:web`, `area:evals`
- `priority:p0`, `priority:p1`, `priority:p2`

### Suggested priority bands
- **P0** = must land before Superinvestor can credibly claim “best” progress
- **P1** = important next-layer capability
- **P2** = useful after the core harness is already trustworthy

---

## Epic 0 — Freeze product definition and core contracts

**Outcome:** the team agrees on what product is being built, for whom, and what the core system objects are.

### Issue 0.1 — Write the product positioning brief
**Priority:** P0  
**Why:** avoid building a vague hybrid of stock chatbot, quant lab, and broker bot.

**Acceptance criteria**
- define the target category as an open-source AI finance harness
- define the primary user and top jobs-to-be-done
- define explicit non-goals for this stage
- document the “best” claim boundaries honestly

### Issue 0.2 — Define and version the canonical artifact schemas
**Priority:** P0  
**Why:** later features depend on shared objects, not ad hoc dictionaries and markdown.

**Acceptance criteria**
- version schemas for `AnalysisRun`, `EvidenceRef`, `CalcResult`, `RecommendationIntent`, `PortfolioIntent`, `EvalRun`, `DecisionManifest`, and `ApprovalRecord`
- store schema versions with every persisted artifact
- reject incompatible payloads with clear errors

### Issue 0.3 — Define the end-to-end research-to-action contract
**Priority:** P0  
**Why:** research, replay, and deployment must share one consistent contract.

**Acceptance criteria**
- document the flow from data fetch → analysis → synthesis → evaluation → portfolio decision → paper/live action
- define which steps are deterministic vs LLM-driven
- define the required inputs/outputs for each stage

### Issue 0.4 — Establish architecture boundaries by package ✅ DONE (2026-04-23)
**Priority:** P0  
**Why:** the current repo already has clean package structure; this needs to become a hard rule before growth adds drift.

**Status:** Completed via `docs/architecture.md` and `tests/test_architecture/test_package_boundaries.py`.

**Acceptance criteria**
- document package ownership for `agents`, `data`, `engine`, `models`, `store`, `tui`, and `web`
- define import boundary rules
- add at least one architecture note describing subsystem responsibilities

### Issue 0.5 — Add schema compatibility and artifact round-trip tests
**Priority:** P0  
**Why:** versioned objects are useless unless they remain readable and stable.

**Acceptance criteria**
- add tests that serialize and deserialize all canonical artifact types
- add fixtures for at least one old-version artifact format
- fail loudly on breaking schema changes

---

## Epic 1 — Make analysis outputs structured, cited, and auditable

**Outcome:** an analysis run becomes a reproducible research artifact instead of mostly freeform prose.

### Issue 1.1 — Replace loose analyst outputs with typed result models
**Priority:** P0

**Acceptance criteria**
- each analyst returns a structured payload in addition to narrative text
- structured payloads are validated by Pydantic models
- pipeline and UI can consume the typed payloads without parsing brittle prose

### Issue 1.2 — Add a first-class evidence reference model
**Priority:** P0

**Acceptance criteria**
- create a reusable `EvidenceRef` object for filings, news, quotes, macro series, and derived facts
- include source id, citation text or locator, as-of time, and retrieval time
- link evidence refs to analyst claims and final recommendations

### Issue 1.3 — Introduce deterministic finance calculators
**Priority:** P0

**Acceptance criteria**
- move core calculations out of model prose and into deterministic helpers
- cover valuation ratios, growth, margins, return math, and benchmark-relative math
- add unit tests for numeric correctness and edge cases

### Issue 1.4 — Capture per-run manifests in the pipeline
**Priority:** P0

**Acceptance criteria**
- each run records tools called, inputs used, timestamps, prompt/model versions, and derived metrics
- manifests are persisted and retrievable later
- manifest data is visible in debugging and audit flows

### Issue 1.5 — Emit structured synthesizer decisions alongside narrative output
**Priority:** P0

**Acceptance criteria**
- synthesizer returns machine-readable decision fields, not just markdown
- narrative report and decision object are derived from the same validated payload
- backtest logic no longer depends on regex parsing as the primary contract

### Issue 1.6 — Persist and reopen full analysis artifacts
**Priority:** P1

**Acceptance criteria**
- save structured analysis runs, evidence, and manifests in storage
- support loading prior analyses by id or ticker/date
- expose saved analysis history to future CLI/TUI flows

---

## Epic 2 — Build the eval harness

**Outcome:** the team can measure whether changes improve trust, correctness, and decision quality.

### Issue 2.1 — Create the `evals` package and core eval models
**Priority:** P0

**Acceptance criteria**
- add `src/superinvestor/evals/`
- define `EvalRun`, `EvalCase`, `EvalMetric`, and result artifact models
- add a simple CLI entry point to run local eval suites

### Issue 2.2 — Add benchmark runners for core task categories
**Priority:** P0

**Acceptance criteria**
- support at least financial QA, retrieval/evidence quality, numerical correctness, and historical decision replay
- each runner uses versioned fixtures or datasets
- results are saved in a comparable artifact format

### Issue 2.3 — Define the internal regression dataset format
**Priority:** P0

**Acceptance criteria**
- support versioned internal eval cases with expected outputs or scoring rules
- document how contributors add new cases
- store metadata for prompt version, model version, and tool policy

### Issue 2.4 — Add scorecards and report rendering for eval runs
**Priority:** P1

**Acceptance criteria**
- render metrics for citation support, numeric accuracy, decision usefulness, and portfolio impact
- allow side-by-side comparison across two eval runs
- surface failed cases clearly for debugging

### Issue 2.5 — Wire a core eval subset into CI
**Priority:** P0

**Acceptance criteria**
- fast deterministic eval subset runs in CI
- CI fails when critical trust/correctness regressions exceed thresholds
- slower benchmark suites can be run locally or on demand

---

## Epic 3 — Make the data plane point-in-time explicit

**Outcome:** historical replay becomes materially more trustworthy and leakage is easier to detect.

### Issue 3.1 — Define canonical security and entity normalization
**Priority:** P0

**Acceptance criteria**
- normalize ticker/security identity across market, filing, and portfolio layers
- define canonical keys for companies and instruments where possible
- document mapping assumptions and fallback behavior

### Issue 3.2 — Add as-of semantics to every replay-critical data adapter
**Priority:** P0

**Acceptance criteria**
- prices, filings, news, macro, and portfolio/account reads accept explicit as-of inputs where relevant
- adapters document whether they use publication time, event time, or retrieval time
- ambiguous time semantics are removed or labeled clearly

### Issue 3.3 — Split raw payload storage from normalized views
**Priority:** P1

**Acceptance criteria**
- preserve raw upstream payloads for audit and replay where feasible
- build normalized research-ready models separately
- derived views can point back to raw records

### Issue 3.4 — Add leakage guards to backtest and eval execution
**Priority:** P0

**Acceptance criteria**
- backtests fail or warn loudly when required historical guarantees are unavailable
- evals can mark cases as PIT-safe or PIT-limited
- leakage checks are covered by tests

### Issue 3.5 — Expose lineage in analysis and eval artifacts
**Priority:** P1

**Acceptance criteria**
- derived facts can trace back to raw records and timestamps
- lineage is visible in saved manifests or artifact inspection tools
- users can distinguish source-backed claims from model-inferred claims

---

## Epic 4 — Upgrade from stock opinions to portfolio intents

**Outcome:** Superinvestor becomes useful for allocation decisions, not just narrative recommendation generation.

### Issue 4.1 — Define the portfolio intent schema
**Priority:** P0

**Acceptance criteria**
- add typed objects for target weights, rebalance proposals, and optional order suggestions
- document the difference between commentary, recommendation, and portfolio intent
- include confidence, constraints, and rationale links

### Issue 4.2 — Build the execution simulator
**Priority:** P0

**Acceptance criteria**
- simulate fills with commissions, slippage, and basic liquidity constraints
- support cash updates, positions, realized P&L, and unrealized P&L
- add deterministic tests for core accounting flows

### Issue 4.3 — Extend backtests from single-call scoring to portfolio replay
**Priority:** P0

**Acceptance criteria**
- support multi-position portfolio state over time
- evaluate returns, turnover, exposures, and benchmark-relative performance
- keep analysis artifacts linked to resulting portfolio actions

### Issue 4.4 — Add portfolio risk overlays and constraint enforcement
**Priority:** P1

**Acceptance criteria**
- enforce max position size, concentration rules, and turnover limits
- support configurable policy hooks for future risk controls
- rejected intents are persisted with rejection reasons

### Issue 4.5 — Replace the placeholder portfolio command with a real paper portfolio surface
**Priority:** P1

**Acceptance criteria**
- `superinvestor portfolio` shows actual portfolio state
- portfolio state is persisted and reloadable
- TUI has at least a basic portfolio review flow

---

## Epic 5 — Build the supervised paper-trading control plane

**Outcome:** research can flow into reviewable paper actions with guardrails and auditability.

### Issue 5.1 — Add a paper broker/account abstraction
**Priority:** P0

**Acceptance criteria**
- define a broker interface for paper mode first
- support account state, open orders, fills, and portfolio sync
- keep the design extensible for future live adapters

### Issue 5.2 — Add approval workflows before paper execution
**Priority:** P0

**Acceptance criteria**
- portfolio proposals require explicit approval before orders are submitted
- approval records store actor, timestamp, and linked rationale
- rejected proposals remain visible for later review

### Issue 5.3 — Add guardrails, kill switches, and policy gates
**Priority:** P0

**Acceptance criteria**
- configurable controls exist for max order size, total exposure, and emergency stop
- policy failures prevent submission and log a clear reason
- policies are testable without live broker dependencies

### Issue 5.4 — Link monitoring to thesis drift and paper review flows
**Priority:** P1

**Acceptance criteria**
- monitors can trigger re-analysis or review tasks for price, news, filings, or thesis violations
- paper positions can show active alerts and drift status
- monitor-triggered actions are written to the audit trail

### Issue 5.5 — Persist end-to-end paper action audit trails
**Priority:** P0

**Acceptance criteria**
- every paper action links back to analysis, evidence, portfolio intent, approval, and simulated execution outcome
- audit records are queryable by ticker, run id, and date
- the system can reconstruct “why this paper trade happened” later

---

## Epic 6 — Build workspace and operator review surfaces

**Outcome:** serious repeated work becomes easier because artifacts can be reviewed, compared, and audited.

### Issue 6.1 — Add an artifact index and history layer
**Priority:** P1

**Acceptance criteria**
- users can list saved analyses, evals, portfolio proposals, paper actions, and approvals
- artifacts are filterable by ticker, date range, and type
- artifact ids are stable and user-visible

### Issue 6.2 — Add compare/diff workflows
**Priority:** P1

**Acceptance criteria**
- compare two analyses of the same ticker at different times
- compare two eval runs or model/prompt versions on the same case set
- surface changed evidence, changed conclusions, and changed portfolio actions

### Issue 6.3 — Expand TUI support for operator workflows
**Priority:** P1

**Acceptance criteria**
- TUI supports at least research review, eval review, portfolio review, and approval actions
- users can open a saved artifact and inspect linked evidence/manifests
- operator-critical flows do not require reading raw DB rows or JSON files

### Issue 6.4 — Add a minimal web review surface only for high-value workflows
**Priority:** P2

**Acceptance criteria**
- web UI is limited to artifact review, compare views, and paper approval/audit needs
- web work does not duplicate unstable backend contracts
- backend APIs reused by the web layer are versioned and documented

### Issue 6.5 — Surface prompt/model/version metadata across the workspace
**Priority:** P1

**Acceptance criteria**
- users can see which prompt/model/tool policy produced an artifact
- workspace surfaces version metadata consistently
- compare flows can group or filter by version

---

## Epic 7 — Prepare for tightly controlled live operation

**Outcome:** the system becomes capable of narrow, human-governed live usage without pretending to be a fully autonomous trading bot.

### Issue 7.1 — Separate paper and live environments end to end
**Priority:** P1

**Acceptance criteria**
- live and paper records are stored separately or clearly partitioned
- configuration, credentials, and execution paths differ by environment
- accidental cross-environment actions are hard to trigger

### Issue 7.2 — Add stronger secrets, policy, and approval controls for live mode
**Priority:** P1

**Acceptance criteria**
- live mode requires stricter approval steps than paper mode
- secret handling and rotation guidance are documented
- policy controls can be audited after the fact

### Issue 7.3 — Add immutable decision manifests and disclosure labeling
**Priority:** P1

**Acceptance criteria**
- live and paper decisions carry immutable manifests or append-only audit records
- hypothetical, paper, and live performance records are clearly labeled
- result views include assumptions and disclosure text where appropriate

### Issue 7.4 — Write operational runbooks and readiness checklists
**Priority:** P1

**Acceptance criteria**
- runbooks exist for data outages, model outages, broker outages, and market stress conditions
- live readiness checklist must be passed before enabling live mode
- operational docs describe rollback and safe-disable procedures

---

## Recommended milestone grouping

### Milestone M1 — Trustworthy analysis
Ship:
- Epic 0
- Epic 1

### Milestone M2 — Measurable quality
Ship:
- Epic 2
- Issue 3.4

### Milestone M3 — PIT-safe replay
Ship:
- remaining Epic 3 issues

### Milestone M4 — Portfolio usefulness
Ship:
- Epic 4

### Milestone M5 — Paper deployment
Ship:
- Epic 5

### Milestone M6 — Operator workflow
Ship:
- Epic 6

### Milestone M7 — Controlled live readiness
Ship:
- Epic 7

---

## Recommended first 10 issues to open

If you want the fastest path from plan to execution, open these first:

1. Issue 0.1 — Write the product positioning brief
2. Issue 0.2 — Define and version the canonical artifact schemas
3. Issue 0.3 — Define the end-to-end research-to-action contract
4. Issue 0.5 — Add schema compatibility and artifact round-trip tests
5. Issue 1.1 — Replace loose analyst outputs with typed result models
6. Issue 1.2 — Add a first-class evidence reference model
7. Issue 1.3 — Introduce deterministic finance calculators
8. Issue 1.4 — Capture per-run manifests in the pipeline
9. Issue 1.5 — Emit structured synthesizer decisions alongside narrative output
10. Issue 2.1 — Create the `evals` package and core eval models

These 10 issues establish the foundation for nearly every later phase.

---

## Explicitly deferred work

Do not prioritize these ahead of the core backlog:
- more agent personas without evidence they improve evals
- broad multi-asset expansion before the equity workflow is trustworthy
- heavy dashboard work before artifact contracts stabilize
- alt-data expansion before point-in-time lineage is strong
- unsupervised live trading

