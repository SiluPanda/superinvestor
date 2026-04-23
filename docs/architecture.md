# Superinvestor Architecture Boundaries

_Date: 2026-04-23_

This note defines package ownership and import boundaries for the Superinvestor codebase.
It implements the Phase 0 planning item to establish repo conventions before the project grows further.

---

## Design goals

The package layout should make the dependency direction obvious:

1. **Models are the foundation** — shared contracts and enums should stay dependency-light.
2. **Data and store are infrastructure layers** — they should not reach upward into orchestration or UI.
3. **Agents and engine are orchestration layers** — they can compose lower layers but should not become the storage or UI layer.
4. **TUI/Web are presentation layers** — they sit at the edge of the system.
5. **MCP is an integration boundary** — it should remain isolated from application policy.

---

## Package ownership

| Package | Responsibility | Notes |
|---|---|---|
| `models` | Shared typed contracts, enums, and base models | Foundation layer used everywhere else |
| `config` | Application settings and config loading | May depend on `models`, but should stay thin |
| `data` | External market/filings/macro provider adapters and rate limiting | Converts upstream APIs into normalized models |
| `store` | Persistence and retrieval of application artifacts | Owns DB-facing storage concerns |
| `mcp` | MCP client/session integration | Isolated external tool bridge |
| `agents` | Prompts, provider adapters, and tool-execution wrappers | LLM orchestration layer |
| `engine` | Deterministic workflow orchestration, replay, monitoring, and backtests | Application control plane |
| `tui` | Terminal user experience | Presentation layer |
| `web` | Web-facing presentation/API surface | Presentation layer |

---

## Import boundary rules

### Hard rules

These rules should stay true unless the architecture note is intentionally revised:

- `models` must not depend on any other internal Superinvestor package.
- `config` may depend on `models`, but not on orchestration or UI layers.
- `data` may depend on `models` and other `data` modules only.
- `store` may depend on `models` and other `store` modules only.
- `mcp` should remain isolated and must not depend on `agents`, `engine`, `store`, `tui`, or `web`.

These foundational rules are enforced by automated tests.

### Guidance rules

These are architectural expectations for higher-level packages:

- `agents` may depend on `config`, `data`, `engine` helpers, `mcp`, `models`, and `store` as part of orchestration.
- `engine` may depend on `agents`, `config`, `data`, `models`, and `store`, but should not depend on `tui` or `web`.
- `tui` and `web` are top-level presentation packages and may depend on application services beneath them.
- New cross-package imports should follow the downward dependency direction when possible.

---

## Dependency direction

Preferred dependency flow:

`models` ← `config` / `data` / `store` ← `agents` / `engine` ← `tui` / `web`

`mcp` stays beside the main flow as an integration boundary.

---

## Change policy

If a future feature requires breaking one of the hard rules:

1. update this architecture note first,
2. explain why the boundary must move,
3. update the architecture test expectations in the same change,
4. keep the exception as narrow as possible.

That makes boundary changes explicit instead of accidental.
