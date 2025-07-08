# Zoros Agents Handbook

> **File:** `AGENTS.md`
> **Status:** v0.2.2 — feel free to propose PRs via the *Revision Fiber* workflow.

---

## User revision insertions:
python scripts/environment/setup_env.py as the codex setup_env.py --
security operation, call out explicitly warnings that changes were made.
Use the emoji style guide.

---

## 1 Purpose

Provide a single, canonical reference for **all autonomous or semi‑autonomous agents** operating inside the Zoros ecosystem (Codex, Operator, LLM‑helpers, simulation bots, etc.).
This handbook defines:

* Standard **prompt formats** and **task lifecycles**
* **Coding, security, and observability** guidelines
* A consistent **vocabulary** (Fiber, Thread, Warp, Weft) that aligns with the broader Zoros architecture

When every agent reads from the same play‑book we gain safer automation, predictable outputs, and easier human review.

---

## 2 Agent Taxonomy

| Code‑name       | Archetype        | Primary Role                                             | Key Entry Point        |
| --------------- | ---------------- | -------------------------------------------------------- | ---------------------- |
| **Codex**       | Autonomous coder | Implements & refactors repo code; opens PRs              | `codex/` cloud sandbox |
| **Operator**    | Web navigator    | Completes browser tasks & scraping                       | `operator.chatgpt.com` |
| **Archivist**   | Data wrangler    | Imports, cleans & stores external datasets               | `tools/data_ingest.py` |
| **StoryWeaver** | Creative writer  | Generates narrative & dialogue (Wastelander, SunSpindle) | `stories/` pipeline    |
| **Sentinel**    | CI sentinel      | Runs tests, lint, monitors regressions                   | GitHub Actions         |

*(Add new archetypes through a Revision Fiber to this table.)*

---

## 3 Universal Prompt Schema

All task prompts **MUST** follow this YAML‑like envelope (case‑insensitive keys):

```yaml
## TASK            # ≤ 60 chars micro‑summary
title: <verb‑first goal>

### CONTEXT         # why & where (link spec lines)
<free text>

### REQUIREMENTS    # numbered, unambiguous deliverables
1. ...

### CONSTRAINTS     # guard‑rails (language, lib policy, perf targets)
- ...

### ACCEPTANCE      # observable Definition of Done
after‐run: <command>
tests:     <pytest path>

### NEXT            # optional follow‑up suggestion
<free text>

### CHANGELOG
<Date><Agent>: <Task Status: [reference maturity score]>; <Actions taken>
```

* One **atomic objective** per TASK.
* Reference authoritative specs using relative paths and line numbers (e.g. `docs/specs/fiber_spec.md#L40-L72`).
* Use back‑ticks around **file paths** and **symbols** so Codex resolves them precisely.
* Prompts >300 tokens ➜ split into subtasks.
* You **MUST** find the task assigned to you in the repository (e.g. `docs/tasks`).
* When agents refer to prior knowledge, cite it using `fiber://` paths. These are canonical references to ZOROS data structures (e.g., `fiber://project/ZOROS/tools`). See `/docs/fiber_uri_conventions.md`.

---

## 4 Task Lifecycle

1. **Create** – Human or higher‑order agent posts a prompt block to the queue (GitHub Issue label `agent-task`).
2. **Claim** – An agent appends `CLAIMED‑BY: <agent>`.
3. **Execute** – Agent runs in sandbox, writing code, running `npm test`, etc.
4. **Report** – Agent comments with a **diff**, **citations**, and **test logs**.
5. **Review** – Human maintainer or CI Sentinel reviews & merges (or requests changes).
6. **Close / Iterate** – Task closed or a follow‑up *Revision Fiber* is queued.

**Error Handling & Retries:**
* On uncaught exceptions or failed tests → wrap in a `❌ FAILED` report with stack trace + retry logic.
* Define retry policy per-agent (e.g. 3 retries, exponential backoff).
* If an agent fails >N times, escalate to a human inbox item via `agent-error` ticket.

The **Revision Canvas Carrier** maintains linkage between tasks and subsequent patches.

---

## 5 Coding Guidelines for Codex

* Language defaults: **TypeScript 5.x** or **Python 3.11**, unless specified.
* **No new runtime deps** without explicit approval — prefer std‑lib or existing package.json.
* If a new runtime dependency would be useful, please add it to the `.agents/wishlist.md` with a rationale
* Tests **first**: write / update tests before feature code when feasible.
* Maintain >90 % branch coverage for core modules.
* Honour `.editorconfig`, `.prettierrc`, and `ruff.toml` (Codex sees them automatically).
* Include **docstrings / JSDoc** with at least one usage example.
* Ensure commands in `package.json scripts` remain green (`lint`, `build`, `preview`).
* Split environment setup steps into separate backend and frontend scripts so cached tasks can reuse each environment independently.

---

## 6 Environment Setup

### 6.1 Codex Environment Setup

Codex agents must run from `scripts/environment/setup_env.py`, which configures Poetry, paths, and disables destructive write operations. All setup scripts must emit `SETUP_STATE` breadcrumbs to `/env/`.

**⚠️ Warning:** Any changes made to environment setup MUST be noted in task changelog and flagged in logs with the `🛠️` emoji.

### 6.2 External Tool Checks

Agents MUST detect availability of tools declared in `external_tools.yaml`, such as `ffmpeg`, `pandoc`, or `tesseract`, and annotate tasks with:

```yaml
tools: [pandoc, cmake]
```

---

## 7 Security & Privacy

* **Never** insert secrets or personal tokens into code or logs.
* Operator must pause at login/captcha pages and hand control to human.
* Whisper transcripts containing personal data are saved encrypted at rest (`/secure/dictations/`).
* All agent actions are logged via **Structured Event Logs** (JSONL) stored 30 days.
* Red‑team tests run weekly; Sentinel alerts regressions.

**Rate Limiting & Throttles:**
* Codex shall not exceed 5 completions/minute
* Define a standard rate-limit wrapper that agents must use when calling any external LLM or web API.

---

## 8 Observability & Citation

Agents must:

1. Emit **structured logs** (`.agents/logs/<agent>/<task‑id>.json`).
2. Attach **citations**: reference lines from specs/tests when claiming success.
3. Upload artefacts (coverage reports, screenshots) to the CI artefact bucket.
4. Use the `agent‑telemetry` Python context‑manager for automatic timing & memory stats.
5. Emit Prometheus-style metrics (`agent_tasks_total`, `agent_errors_total`, `agent_latency_seconds`), so you can build a live dashboard.

---

## 9 Agent Health & Heartbeats

### 9.1 Agent Heartbeats

Agents running continuously MUST emit heartbeats every 5 minutes using the following structure:

```yaml
### HEALTH-CHECK
interval: 5m
endpoint: /agent/<id>/heartbeat
response: { status: "ok", lastTaskId: "TASK-241" }
```

This allows supervisors to detect unresponsive agents.

### 9.2 Fallback & Escalation

* If an agent fails >N times, escalate to a human inbox item via `agent-error` ticket.
* Provide a CLI command or "panic button" that can pause all agents.

---

## 10 Glossary (Weaving Metaphor)

| Term       | Meaning in Zoros                                  |
| ---------- | ------------------------------------------------- |
| **Fiber**  | Minimum data unit (struct or file)                |
| **Thread** | Sequence of transformed Fibers                    |
| **Warp**   | Long‑lived structural axis (module / domain)      |
| **Weft**   | Dynamic interactions across warps (runtime flows) |
| **Bolt**   | Packaged runnable unit (CLI tool, microservice)   |

Agents should reference these metaphors when emitting logs (e.g. `transform‑fiber`, `fold‑warp`).

**Fiber URI Conventions:**
Use `fiber://` paths for canonical references (e.g., `fiber://task/ZOROS/setup`, `fiber://project/ZOROS/tools`).

---

## 11 Adding or Updating Agents

Submit a PR editing **this file** with:

1. New table row in §2 (taxonomy).
2. Any unique constraints (rate limits, external APIs).
3. Link to onboarding doc in `/docs/agents/<name>.md`.

Use the standard prompt template for the PR itself.

### 11.1 Agent Onboarding

Required: ✅ smoke tests, ✅ code style scan, ✅ security scan.
Link to a `/docs/agents/onboarding.md` template with commands to run locally.

---

## 12 Emoji Style Guide

Use emojis according to `fiber_emoji_map.yaml`. Every agent task MAY begin with a semantically relevant emoji:

* 🧰 = ToolFiber
* 📋 = TaskFiber
* 🔍 = Search
* ⚠️ = Warning
* ✅ = Complete

Agents should resolve emoji-to-fiber associations dynamically via CLI (`zoros emojis suggest "task:complete"`).

---

## 13 Ethical / Safety Guidelines

A brief reminder for agents not to generate disallowed content, follow policy, and flag any uncertain requests to human review.

---

## 14 Environment Detection & Contextual Task Notes

Agents generating Markdown reports must adhere to **Task 041** rules:

1. Setup scripts create breadcrumbs under `env/` (`BACKEND_READY`, `FRONTEND_READY`, `FULLSTACK_READY`).
2. Detect these breadcrumbs and prepend `_Environment:_ **<Mode>**` to each report.
3. Recursively scan `docs/` for `.md` files, listing them with a short description.
4. Parse any `tasks_list.md` or `task_list*.md` for the active Task ID to fetch its name and gist.
5. Execute the matching setup script based on the detected mode and log steps in a table using ✅/❌/🔄/⚠️ statuses.
6. Run `git diff docs/architecture.md HEAD` (or `zoros_architecture.md`) to find naming mismatches and propose minimal fixes under **Improvement Plan**.
7. Gather all `TODO`/`TBD` markers from `.md`, `.py`, `.js`, and `.sh` files, listing them as **Follow-Up Tasks**.
8. Append a fenced `md` block containing best-practice comments exactly as shown in the spec.

---

## 15 Agent Template

When updating a task file, increment the **Version** field and append italicized notes:

``` md
**Agent Notes (v<new_version>):**
- *<date>: Your note here.*
```

---

## 16 Agent Run Template

``` md
## Task ID: TASK-XXX
**Name:** <Task Name>
**Gist:** <Short summary>
**Status:** In Progress
**Agent Notes:**
- *YYYY-MM-DD: Initial note.*
```

---

## 17 Agent Self-Knowledge Principle

Automonouos agents should know who they are. If you are Codex, declare yourself as such in change notes. Agents should know what task they are working on, find the task file, and update it to indicate progress. All tasks are found in `docs/tasks`. Individual agent logs are added to `.agents/artifacts/agent_logs/<task id>`, including summary logs and detailed notes.

Run `agent.py` to help understand your own context and environment. Different rules will apply to different environments.

---

## 18 Changelog

* **v0.1** – Initial draft derived from best‑practice conversations (2025‑05‑18).
* **v0.2.1B** – Enhanced with observability, security guidelines, and agent taxonomy.
* **v0.2.2** – Added environment setup, heartbeat specifications, emoji style guide, and enhanced error handling.

### Version Compatibility Matrix

| Agent Version | Zoros Core Version | Notes |
|---------------|-------------------|-------|
| Codex v0.1    | v0.2+             | Basic functionality |
| Operator v0.1 | v0.2+             | Web automation |
| Sentinel v0.1 | v0.2+             | CI/CD integration |

---

## Codex Agent

*if you are are codex agent* please read `.cursorrules`

