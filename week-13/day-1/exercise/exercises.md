# Week 13 · Day 1 — Exercise: Expand The Primary Workflow

Week 12 gave you one thin path that runs and proves itself. Today you widen that path into
your capstone's **primary workflow** without losing its trace, tests, or green eval.

**Deliverable:** a completed
[Core Implementation Checkpoint](./core-implementation-checklist.md) plus the corresponding
code, trace, tests, and backlog in your own repository.

**Rule:** keep the green path intact. Do not restart the capstone or spread across several
half-built features.

---

## 1. Baseline before editing

Run the Week 12 slice exactly as it existed on Friday:

1. Send its representative real input.
2. Confirm the output is produced.
3. Open the trace and verify every existing step.
4. Run the offline tests.
5. Run the previously green golden-row eval.
6. Record the results in the checklist.

If the baseline is not green, select the **minimum** lane and stabilize it first. A stable
starting point is more valuable than an additional broken feature.

---

## 2. Pick the next missing core capability

Use your brief, architecture, trace, and golden set—not excitement—to choose it.

Answer:

- What prevents the primary happy path from being complete?
- Which real user need or golden row shows that it matters?
- What is the smallest observable behaviour you can implement today?
- Which new span, event, or test will prove it works?

Examples of the *shape* of a capability, not answers to copy:

- Support: handle one additional representative intent through the same retrieval path.
- Workflow: add the required route or approval transition for the happy path.
- Research: integrate one required fetch/critique step into the existing synthesis path.
- Tool integration: connect the next required operation behind a typed boundary.
- Multi-agent: complete one required hand-off already justified by the architecture.

Backlog secondary journeys, optional tools, UI polish, and speculative refactors.

---

## 3. Implement one boundary at a time

For each addition:

1. Add the smallest boundary or behaviour.
2. Run one representative input.
3. Inspect the trace for the new step.
4. Run offline tests.
5. Rerun existing evals.
6. Commit when green.

Keep the production loop explicit:

```text
input → reason / route → tool boundary → state / context → output
```

Tuesday will decide what the context boundary actually needs. Do not bolt on retrieval or
memory today unless the primary workflow already requires it.

---

## 4. Stop at the appropriate lane

- **Minimum:** slice stable; one core step implemented or made concretely unblocked.
- **Target:** primary happy path runs with required integrations; trace, tests, and existing
  evals remain green.
- **Stretch:** add one scenario or deterministic regression test to the same workflow.

Record the lane reached and the exact next step. Honest progress evidence is the goal—not
matching another learner's feature count.

---

## Troubleshooting

**“My Friday slice no longer works.”**
- Stop expanding. Return to the last green commit, reproduce the baseline, and change one
  thing at a time.

**“The missing capability is too large for today.”**
- Cut it to one observable behaviour at one boundary. Replace “support approvals” with
  “route one representative request to the approval step.”

**“The trace ends before the new step.”**
- Instrument the boundary before debugging its internals. Confirm the request enters and
  the result exits with stable identifiers.

**“The tool works live but offline tests fail.”**
- Keep the integration behind an injectable interface. Update the fake to match the
  contract; do not call the network from tests.

**“The new path works, but the old eval is red.”**
- Treat it as a regression. Compare the baseline and new traces, fix the changed behaviour,
  and do not loosen the existing eval merely to restore green.

**“I have several equally important features.”**
- Pick the one required by the most representative happy path or golden row. Put the rest
  in the visible backlog.

---

## If you finish early

Choose one:

- Add a deterministic regression test for the new capability.
- Run a second representative scenario through the **same** workflow.
- Improve the trace so every boundary records inputs/outputs safely.

Do not start another product flow. Stretch should deepen confidence in the path you built.
