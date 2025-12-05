# Zoros Mission Statement

**Version**: v0.2  
**Last Updated**: 2025-08-16  
**Source**: docs/zoros_chats/Zoros - Fiberize XOROS chat 16AUG2025-B_deduped.md  
**Status**: Draft - Awaiting Review

---

## One-liner
Capture → fibrize → orchestrate — and **plug into the best open-source tools through a trusted gateway**, using hybrid routines that make work repeatable, auditable, and local-first.

## Mission Statement
Zoros turns unstructured thinking (dictations, chats, notes) into **fibers** that form a living memory graph (threads/warps). From that memory, it **orchestrates agents** to deliver software and documents with tests and provenance. A built-in **Open-Source Tool Gateway** evaluates, wraps, and safely runs third-party libraries, while **hybrid routines** split work between LLM reasoning and deterministic steps—so results are consistent, reproducible, and eventually runnable on local models.

---

## Pillars

### 1. Zero-obstruction capture
Dictate or drop anything; Zoros fibrizes it with sources, fold levels, and links.

### 2. Memory graph as ground truth
Decisions, specs, tasks, tests, logs—everything is a fiber with provenance and lineage.

### 3. Mission-anchored execution
Every run starts from a **Thread Head** (mission, constraints, acceptance). Agents must **discover before generate** and raise **Question/Contradiction** fibers instead of guessing.

### 4. Open-Source Tool Gateway (ToolHub)
- **Evaluate** GitHub projects (readme, license, examples, tests, maintenance cadence).
- **Extract I/O contracts** (args/returns, file formats, side effects) into JSON Schema.
- **Scan dependencies & telemetry** (detect network calls, analytics SDKs); propose egress rules and opt-out config.
- **Resolve environments** (check what's already installed; build or reuse venv/conda/docker images; cache layers).
- **Wrap as MCP tools** with typed arguments, examples, and guardrails; publish to a **tool registry** with fitness/safety scores.
- **Monitor updates** and open "upgrade review" fibers when versions shift.

### 5. Hybrid routines (LLM × deterministic)
- **Prototype phase**: LLM drafts a plan, enumerates steps & checks.
- **Programmatic phase**: deterministic executors run steps, verify outputs, and produce artifacts/tests.
- **Dumb-down adapters**: pre-shape problems so **local** or **mini** models can complete them reliably.

### 6. Project & context management
- **Heads dashboard**: see active thread heads (mission, acceptance, latest state) across projects.
- **Authority-ordered context packs**: Head → Spec-of-Record → Registry snippets → targeted code; drop low-priority first on overflow.
- **Checkpoints** to restate mission & acceptance; contradiction detection baked in.

### 7. Quality, provenance, privacy
Contract tests before promotion, **provenance headers** on files/commits, **no surprise telemetry**, snapshot-pinned models, offline/OSS fallbacks.

---

## Design Principles

- **Fibers are the unit of truth.** Everything (specs, tasks, decisions, tests, logs) is a fiber with provenance.
- **Context packs by authority.** Head → Spec-of-Record → Registry snippets → targeted code.
- **Discover before generate.** Exact/semantic search + registry produce a **Reuse Report** before writing.
- **Provenance everywhere.** Files, commits, and artifacts carry machine-readable origin (ai|human|mixed) and review status.
- **Small, reversible steps.** Frequent commits, crisp PRs, and automated promotion checks.
- **Extensible by MCP.** Tools are described, typed, and replaceable.

---

## MVP Slices

### ToolHub v0.1
CLI that ingests a GitHub repo → emits a registry "tool card" (I/O schema, setup plan, telemetry findings, readiness score) → optional MCP wrapper scaffold.

### Hybrid Routine v0.1
A routine that runs: Plan (LLM) → Execute (scripts) → Verify (tests) → Promote (docs+registry). Fails closed if tests or provenance are missing.

### Heads Dashboard v0.1
Web view of Thread Heads + Question/Contradiction inbox; single-click context pack preview.

### Context Pack Builder v0.1
Deterministic packing by authority; logs an audit trail for every agent run.

---

## Success Metrics

- **Time to first successful run** of a new OSS tool via ToolHub.
- **Reuse rate** (percent of tasks solved via registered tools vs net-new code).
- **Local-model completion share** on hybrid routines.
- **Context overflow incidents** and "drift" defects (downward trend).
- **Vibeslop backlog** (unpromoted drafts) trending down.
- **Privacy score** (tools with zero egress by default) trending up.

---

## Mission Head Fiber (YAML)

```yaml
fiber: MissionHead
project: Zoros
version: 0.2
mission: >
  Capture ideas with zero friction, fibrize them into a memory graph,
  orchestrate agents to deliver tested artifacts, and integrate open-source tools
  through a trusted gateway—using hybrid routines that balance LLM reasoning with
  deterministic steps, local-first and privacy-first.

principles:
  - Discover-before-generate
  - Authority-ordered context packs
  - Provenance everywhere
  - Promotion only after tests/docs/registry
  - No-surprise telemetry; offline/OSS fallbacks

pillars:
  - Zero-obstruction capture
  - Memory graph (fibers→threads→warps)
  - Mission-anchored execution
  - Open-Source Tool Gateway (evaluate, wrap, enforce safety)
  - Hybrid routines (LLM plan → deterministic exec)
  - Heads dashboard & contradiction inbox
  - Local-first privacy, snapshot-pinned models

mvp:
  toolhub: v0.1 (repo intake → tool card → MCP scaffold)
  routines: v0.1 (Plan→Execute→Verify→Promote)
  context_pack_builder: v0.1
  heads_dashboard: v0.1

metrics:
  ttf_run_tool: minutes
  reuse_rate: percent
  local_model_share: percent
  context_drift_incidents: count
  vibeslop_backlog: count
  privacy_zero_egress_tools: count
```

---

## Version History

### v0.1 (Initial Draft)
- Basic capture → fibrize → orchestrate mission
- Focus on memory graph and agent orchestration
- Core design principles established

### v0.2 (Current)
- Added Open-Source Tool Gateway (ToolHub) concept
- Introduced hybrid routines (LLM × deterministic)
- Expanded to include context management and quality gates
- Added specific MVP slices and success metrics
- Included Mission Head fiber format

---

## Non-goals (for focus)

- Not a general chat app; it's a **mission runner**.
- Not an IDE replacement; it **drives** IDEs/agents.
- Not a telemetry platform; observability stays **local and explicit**.

---

*This document should be referenced by all agents and updated through the Revision Fiber workflow.*





