# Capstone Foundation — Acceptance Checklist

> This is the **definition of done** for your skeleton. There is no template to fill and no repo to clone
> — you build your own, from scratch, in whatever stack your architecture implies. The skeleton is done
> when every box below is true. **No features yet** — that is correct.

**Repo:** _link to your capstone repo_
**Author:** _your name_
**Date:** _today_

---

## The six acceptance criteria

- [ ] **Runs from a clean clone.** A fresh checkout installs and runs with no errors. Dependencies are
  pinned so someone else could reproduce your environment. (Test it: clone into a *new* folder and run.)
- [ ] **Secrets in `.env`.** Any API key or token lives in a `.env` file that is gitignored. Nothing
  secret is committed — check `git log` / `git status`.
- [ ] **A no-op run emits a trace.** An echo/do-nothing run (input → agent does nothing → output) already
  produces one readable trace, with a span (or a structured log line) per step.
- [ ] **One real tool is wired.** The first tool your architecture named is integrated behind a clean
  boundary (a custom function or an MCP tool), callable by the agent.
- [ ] **An offline test passes.** At least one test runs green with a **fake injected** in place of the
  real tool — no network, no API key, deterministic.
- [ ] **Tool execution is contained.** Tool / generated-code execution can't reach your host, files, or
  secrets beyond what it needs (isolation scaled to the tool's risk).

### In-class minimum (rest can finish by end of day)

- [ ] **Runs from a clean clone**, and
- [ ] **a no-op run emits a trace.**

If you have those two by the end of the block, you are on track. The tool + offline test can spill into
the afternoon.

---

## "Your stack may vary" — a starting-point matrix

You choose the stack. This maps each archetype to a **likely** first tool and a sensible first trace
target, to unstick you — not to prescribe. Your architecture is the source of truth.

| Archetype | Likely first tool to wire | Sensible no-op / first trace | Sandbox concern |
| --- | --- | --- | --- |
| **Support assistant** | a retrieval/search call over your docs | echo the user's question, trace the (empty) retrieval step | low — read-only; keep keys out of tool scope |
| **Workflow / automation** | the first system it writes to (read-only first) | echo a fake task, trace the "would-do" step (no write yet) | medium — guard the write path; dry-run first |
| **Research / analysis** | a document/web fetch (or local corpus read) | echo a query, trace the fetch step | low–medium — sanitise fetched content |
| **Tool / integration** | the primary external API (read endpoint first) | echo a request, trace the API-call span | medium — scope the token minimally |
| **Multi-agent** *(stretch)* | one worker's single tool (build one agent first!) | echo through one agent, trace its one step | as per that one tool |

> Whatever your stack: the **entrypoint can be an echo**, the **tool starts read-only**, and the **test
> fakes the tool**. Get those green first; realism comes later in the week.

---

## Definition of done, in one line

> A teammate could **clone your repo fresh, run it, watch a no-op emit a trace, and run one offline test
> green** — without a single feature built yet.
