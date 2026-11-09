# Core Implementation Checkpoint

> Expand the Week 12 slice; do not restart it. Choose the pace bar that matches your
> current state, preserve evidence, and stop with a green state plus a clear next step.

**Repo:** _link_
**Selected lane:** Minimum / Target / Stretch
**Primary happy path:** _one sentence_
**Today's missing core capability:** _one capability_
**Evidence it matters:** _brief, golden row, trace, or user need_

---

## Before editing: establish the baseline

- [ ] The Week 12 slice runs end to end.
- [ ] Its trace is readable.
- [ ] Its offline tests pass.
- [ ] Its previously green eval still passes.
- [ ] I saved or recorded the baseline result.

If these are not true, choose the **minimum** lane and stabilize the slice first.

---

## Choose one pace bar

### Minimum — protect tomorrow's dependency

- [ ] The original slice is stable and traced.
- [ ] I implemented one missing core step **or** reduced it to a concrete, unblocked task.
- [ ] I can name the exact next command, file, or boundary to work on.

### Target — intended end-of-day outcome

- [ ] One representative primary happy path runs end to end.
- [ ] Its required primary integration(s) are real, not hard-coded gaps.
- [ ] Every new step appears in the trace.
- [ ] Existing green evals remain green.
- [ ] Offline tests still pass without network access.

### Stretch — deepen the same workflow

Complete the target, then choose **one**:

- [ ] A second representative scenario passes through the same workflow.
- [ ] I added a deterministic regression test for the new capability.

Stretch does **not** mean starting a second product flow.

---

## Scope guardrail

Build now only when the capability:

- [ ] is required by the primary happy path;
- [ ] is supported by evidence from the brief, golden set, trace, or user need;
- [ ] can be traced and tested today.

Everything else goes here:

1. _highest-priority backlog item_
2. _next backlog item_
3. _later / polish_

---

## Checkpoint evidence

- **Command or interaction that runs the workflow:** _…_
- **Trace/run identifier or screenshot location:** _…_
- **Offline test result:** _…_
- **Eval result before → after:** _…_
- **Green commit:** _commit hash_
- **Exact next step:** _one concrete action_

## Definition of a strong checkpoint

> The workflow is wider without becoming less trustworthy: it runs, every new step is
> visible, previous evidence stays green, and unfinished work is explicit.
