# Superinvestor Development Plan

_Date: 2026-04-23_
_Source: `best.md` research plan, translated into an execution roadmap_

---

## 1) What this plan assumes

`best.md` is a research plan, not a build plan. This document converts its core conclusions into a phased development roadmap.

It assumes Superinvestor should aim to become the **best open-source AI finance harness** for US equity research, evaluation, portfolio decisioning, and supervised paper/live deployment — not a generic stock chatbot and not a pure quant backtester.

### Current baseline
Superinvestor already has a meaningful alpha foundation:
- multi-analyst AI research pipeline
- historical backtest flow
- monitoring/watcher system
- CLI + TUI surface area
- typed models, stores, and provider abstractions
- passing automated test suite (`234 passed` as of 2026-04-23)

### Biggest current gaps
The repo appears strongest in **analysis orchestration**, but still lacks the deeper platform layers needed to credibly claim “best”:
- structured evidence/provenance contracts
- benchmark/eval harness as a first-class subsystem
- finance-grade point-in-time data guarantees
- portfolio-level decision and execution modeling
- paper-trading control plane
- governance, approval, and audit layers
- durable research/workspace artifacts

---

## 2) North-star product goal

Build a finance harness that can do all of the following under one reproducible contract:

1. produce evidence-backed research
2. measure quality with rigorous evals
3. translate analysis into portfolio-aware decisions
4. replay those decisions historically without hidden leakage
5. deploy them to supervised paper/live workflows with audit trails

If a feature does not strengthen one of those five steps, it should be deprioritized.

---

## 3) Guiding product principles

Development should follow these principles from `best.md`:
- **Trust beats raw generation quality**
- **Evaluation is a moat**
- **Point-in-time discipline is non-negotiable**
- **Portfolio usefulness matters more than single-ticker eloquence**
- **Research-to-live consistency matters more than demo polish**
- **Deterministic tools should own calculations, state transitions, and risk rules**
- **Open-source leverage comes from transparency, reproducibility, and extensibility**

---

## 4) Phase summary

| Phase | Theme | Main outcome |
|---|---|---|
| Phase 0 | Definition freeze + core contracts | Lock target user, product category, and system contracts |
| Phase 1 | Evidence-backed research core | Every analysis becomes structured, cited, and auditable |
| Phase 2 | Eval harness | Quality becomes measurable and regression-tested |
| Phase 3 | Point-in-time data plane | Historical replay becomes materially more trustworthy |
| Phase 4 | Portfolio + execution engine | Output shifts from commentary to portfolio intent |
| Phase 5 | Paper-trading control plane | Supervised paper deployment becomes real |
| Phase 6 | Workspace + review surfaces | Research, eval, and decisions become inspectable and shareable |
| Phase 7 | Controlled live readiness | Human-approved live operation becomes possible |

---

## 5) Phased roadmap

## Phase 0 — Definition freeze and system contracts

### Objective
Prevent the team from building the wrong product quickly.

### Build
- Finish the research-to-product translation from `best.md` into explicit decisions:
  - target category
  - primary user
  - core jobs-to-be-done
  - what “best” means operationally
- Define the canonical platform objects:
  - `AnalysisRun`
  - `EvidenceRef`
  - `CalcResult`
  - `RecommendationIntent`
  - `PortfolioIntent`
  - `EvalRun`
  - `DecisionManifest`
  - `ApprovalRecord`
- Define one end-to-end contract from:
  - data fetch
  - research
  - synthesis
  - scoring
  - portfolio decision
  - paper/live action
- Write the versioned schema rules for all saved artifacts.
- Establish repo conventions for where each subsystem lives: ✅ DONE (2026-04-23; see `docs/architecture.md` and `tests/test_architecture/test_package_boundaries.py`)
  - `data/` = source adapters + point-in-time logic
  - `agents/` = LLM orchestration only
  - `engine/` = deterministic decision/eval/backtest logic
  - `models/` = shared typed contracts
  - `store/` = persistence and artifact retrieval
  - `tui/` + `web/` = user surfaces

### Non-goals
- adding new models/providers
- building more agent personas
- UI polish

### Exit criteria
- one-page product positioning is frozen
- core domain objects are versioned and documented
- every later phase has clear ownership boundaries

---

## Phase 1 — Evidence-backed research core

### Objective
Turn the current analysis pipeline into a trustworthy research engine instead of a persuasive text generator.

### Build
- Replace loosely structured analyst output with strict typed result schemas.
- Require every material claim to attach one of:
  - source citation
  - deterministic calculation
  - explicit heuristic label
- Add provenance metadata to all analysis artifacts:
  - source type
  - source identifier / URL / filing accession / series id
  - as-of timestamp
  - retrieval timestamp
  - model version / prompt version
- Add deterministic finance calculators for:
  - growth rates
  - valuation multiples
  - margin trends
  - return math
  - exposure math
  - benchmark-relative calculations
- Split narrative generation from calculation generation.
- Add manifest logging for each run:
  - tools called
  - inputs used
  - derived metrics
  - final recommendation path
- Make synthesizer output both:
  - human-readable report
  - structured machine-readable decision object

### Likely repo areas
- `src/superinvestor/agents/`
- `src/superinvestor/engine/pipeline.py`
- `src/superinvestor/models/analysis.py`
- `src/superinvestor/models/signals.py`
- `src/superinvestor/store/analysis_store.py`

### Exit criteria
- an analysis can be re-opened later with full citations and calculation trace
- recommendation text and structured decision cannot drift from each other
- unsupported claims are detectable in tests/evals

---

## Phase 2 — Eval harness as a first-class subsystem

### Objective
Make Superinvestor measurable, comparable, and improvable.

### Build
- Create a dedicated eval subsystem for at least six categories:
  1. financial QA / extraction
  2. retrieval + evidence quality
  3. numerical correctness
  4. historical decision replay
  5. portfolio-level paper evaluation
  6. quant-code competence
- Add benchmark runners for public and internal tasks.
- Support versioned eval datasets and fixtures.
- Create regression suites that compare:
  - prompts
  - models
  - tool policies
  - retrieval strategies
  - system versions
- Add scorecards for:
  - citation quality
  - answer support coverage
  - numeric accuracy
  - decision usefulness
  - portfolio impact
- Add CI hooks so core eval subsets run automatically before major merges.
- Save every eval run as an artifact with comparable metadata.

### Non-goals
- chasing leaderboard vanity metrics without product relevance
- treating LLM benchmark scores as a substitute for replay and portfolio evaluation

### Likely repo areas
- new `src/superinvestor/evals/` package
- `src/superinvestor/engine/backtest.py`
- `src/superinvestor/store/`
- `tests/` plus benchmark fixtures

### Exit criteria
- model/prompt changes can be compared on the same tasks
- the team can explain whether a change improved trust, not just style
- historical replay metrics are part of normal development discipline

---

## Phase 3 — Point-in-time data plane

### Objective
Upgrade the data layer from “useful for demos and basic replay” to “credible for finance research.”

### Build
- Introduce canonical entity/security normalization.
- Define as-of semantics for every data class:
  - prices
  - corporate actions
  - filings
  - transcripts
  - news
  - macro series
  - portfolio/account state
- Add snapshot/version support for all replay-critical data.
- Add explicit publication/availability timestamps where possible.
- Add leakage guards and validation rules in backtest/eval flows.
- Separate raw source payloads from normalized research-ready views.
- Implement lineage metadata so any derived fact can be traced to raw inputs.
- Expand data adapters only where they support the trust/eval roadmap.

### Likely repo areas
- `src/superinvestor/data/`
- `src/superinvestor/models/market.py`
- `src/superinvestor/models/filings.py`
- `src/superinvestor/store/market_store.py`
- `src/superinvestor/store/filing_store.py`
- `src/superinvestor/engine/clock.py`

### Exit criteria
- every replay-critical read is point-in-time explicit
- backtests fail loudly when required historical guarantees are missing
- data lineage is visible in analysis and eval artifacts

---

## Phase 4 — Portfolio and execution engine

### Objective
Move from single-name commentary to decision-useful portfolio outputs.

### Build
- Define the future unit of decision:
  - start with `target weights` plus optional order suggestions
  - keep freeform commentary secondary
- Implement portfolio state transitions for:
  - cash
  - positions
  - rebalances
  - realized/unrealized P&L
  - exposure limits
- Add execution realism layers:
  - commissions/fees
  - slippage
  - ADV/liquidity limits
  - partial fills
  - borrow/short constraints where supported
- Upgrade backtests from isolated ticker calls to portfolio-level replays.
- Add risk overlays:
  - max position size
  - sector/industry concentration
  - turnover limits
  - stop/exit policy hooks
- Implement the currently missing paper portfolio surface.

### Likely repo areas
- `src/superinvestor/models/portfolio.py`
- `src/superinvestor/store/portfolio_store.py`
- `src/superinvestor/engine/backtest.py`
- new portfolio/execution engine modules
- CLI/TUI portfolio commands

### Exit criteria
- Superinvestor can express a portfolio intent, not just a stock opinion
- replay results reflect basic execution reality rather than only narrative correctness
- paper portfolio state is durable and inspectable

---

## Phase 5 — Paper-trading control plane

### Objective
Close the loop from research to supervised action.

### Build
- Create a reviewable decision pipeline:
  - watchlist / universe
  - analysis
  - ranking / compare step
  - portfolio proposal
  - approval
  - paper execution
  - monitoring / thesis drift checks
- Add broker/account abstraction for paper mode first.
- Add explicit approval gates before order submission.
- Add kill switches and guardrail policies.
- Persist all paper actions with linked evidence and rationale.
- Add monitor-triggered re-analysis based on:
  - price moves
  - filings
  - news
  - thesis violations
  - risk limit breaches

### Non-goals
- fully autonomous trading with no human signoff
- broad broker support before the core workflow is stable

### Exit criteria
- a user can run a supervised paper portfolio end to end
- every paper action is linked to evidence, eval context, and approval state
- drift between research output and paper action is minimized by contract

---

## Phase 6 — Workspace and review surfaces

### Objective
Make the harness usable for serious repeated work, not just one-off command runs.

### Build
- Add durable artifacts and navigation for:
  - research runs
  - thesis records
  - eval runs
  - portfolio proposals
  - paper actions
  - approval history
- Add compare/diff views for:
  - two analyses of the same name at different times
  - two models/prompts on the same task
  - current thesis vs updated evidence
- Expand TUI for review workflows, then add web UI only where it materially improves usability.
- Add saved workflow views:
  - research flow
  - compare/rank flow
  - thesis flow
  - replay/eval flow
  - paper review flow
  - audit flow
- Add prompt/model/version registry surfaced to the user.

### Likely repo areas
- `src/superinvestor/tui/`
- `src/superinvestor/web/`
- `src/superinvestor/store/`

### Exit criteria
- users can inspect and compare artifacts without reading raw logs
- research, eval, and portfolio actions feel like one system instead of separate commands

---

## Phase 7 — Controlled live readiness

### Objective
Enable narrow, serious, human-governed live usage only after the earlier layers are stable.

### Build
- Add live-vs-paper environment separation.
- Add approval roles and stronger policy controls.
- Add secret management, key rotation guidance, and deployment hardening.
- Add live execution audit logs and immutable decision manifests.
- Add performance labeling and disclosures for hypothetical vs paper vs live results.
- Add operational runbooks:
  - degraded data mode
  - model outage mode
  - broker outage mode
  - trade halt / market stress mode

### Important guardrail
Live mode should be introduced as **human-approved and tightly scoped**, not as a fully autonomous agent trader.

### Exit criteria
- live actions are reviewable, reversible where possible, and policy-gated
- the system can clearly distinguish simulated, paper, and live records
- governance is strong enough that the product remains trustworthy under stress

---

## 6) Cross-cutting workstreams that run through every phase

### A. Test and verification discipline
- keep unit/integration tests green
- add golden artifacts for research/eval outputs
- add schema compatibility tests
- add replay determinism tests where feasible

### B. Versioning and reproducibility
- version prompts, models, eval datasets, schemas, and manifests
- make historical artifacts readable even after schema evolution

### C. Cost and latency management
- instrument token cost, tool latency, and run duration
- route deterministic work away from LLMs
- treat expensive agent decomposition as opt-in, not default

### D. Documentation
- maintain architecture notes after each phase
- document trust model and known limits honestly
- document which claims are supported vs experimental

### E. Open-source leverage
- keep core contracts and eval tooling transparent
- prefer extensible adapters over hard-coded vendor assumptions
- make contributor entry points obvious

---

## 7) What should be built later, not now

To stay aligned with `best.md`, the roadmap should explicitly defer these until the core harness is credible:
- broad multi-asset expansion beyond the core equity workflow
- flashy autonomous multi-agent swarms without eval justification
- premature enterprise features not tied to trust/eval/governance
- heavy web/dashboard investment before the artifact model is solid
- alt-data expansion before point-in-time discipline is strong
- full live trading autonomy

---

## 8) Suggested milestone gates

| Milestone | What must be true |
|---|---|
| M1: Trustworthy analysis | Every report is structured, cited, and reproducible |
| M2: Measurable quality | Benchmark and replay suites exist and influence development |
| M3: PIT-safe replay | Historical evaluation has explicit data lineage and leakage controls |
| M4: Portfolio usefulness | The system outputs portfolio intents and simulates them realistically |
| M5: Paper deployment | End-to-end supervised paper trading works with audit trails |
| M6: Operator workflow | Users can review, compare, approve, and audit in one workspace |
| M7: Live readiness | Limited live operation is policy-gated and operationally safe |

---

## 9) Recommended build order

If execution capacity is limited, prioritize in this exact order:

1. **Phase 0** — freeze product and contracts
2. **Phase 1** — make outputs trustworthy
3. **Phase 2** — make improvements measurable
4. **Phase 3** — make replay finance-grade
5. **Phase 4** — make outputs portfolio-useful
6. **Phase 5** — make paper deployment real
7. **Phase 6** — make the workflow durable and reviewable
8. **Phase 7** — only then consider controlled live readiness

That order matters. Without it, Superinvestor risks becoming impressive-looking but strategically hollow.

---

## 10) Definition of success

Superinvestor should only claim to be the best open-source AI finance harness when it can credibly demonstrate all of the following:
- its research is evidence-backed
- its quality is benchmarked and regression-tested
- its historical replay is point-in-time disciplined
- its outputs are portfolio-aware
- its paper/live actions are governed by clear controls
- its artifacts are transparent enough for others to audit, extend, and trust

