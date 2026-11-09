# Week 13 · Day 4 — Architecture Refinement & System Integration

Today you turn one midterm finding into a measurable architecture hypothesis and implement
the smallest change that can test it.

## Deliverables

- completed [Architecture Refinement Record](./architecture-refinement-template.md);
- completed [Refinement Checklist](./refinement-checklist.md);
- updated architecture diagram in your repository;
- trace/test/eval evidence appropriate to your pace.

## 1. Select one evidence trigger

Review:

- the midterm trace and eval;
- your known limitation or top risk;
- the classified feedback log;
- observed coupling, latency, cost, or failure behavior.

Choose one high-value signal. Link the artifact and state what it shows. Do not begin with a
pattern or technology.

## 2. Preserve the baseline

Before editing:

1. record the current green commit;
2. run the representative primary path;
3. save the relevant trace/eval/measure;
4. name the regression checks that must remain green.

## 3. Write the hypothesis

Use:

> Because **[evidence]**, changing **[responsibility / component / boundary]** should improve
> **[named measure]** without breaking **[primary workflow / regression guard]**.

If “improve” cannot be measured, tighten the hypothesis before coding.

## 4. Choose one refinement track

- simplify responsibilities or boundaries;
- improve routing or workflow state;
- improve context/retrieval quality;
- reduce cost or latency;
- strengthen tool contracts;
- introduce one earned multi-agent decomposition.

### Multi-agent gate

Another agent is appropriate only when evidence supports:

- a separable responsibility;
- specialized context/tools, useful parallelism, or routing value;
- a measurable benefit that can outweigh coordination cost.

First ask whether a deterministic tool, typed function, or step in the current loop solves
the problem more simply. If it does, use that boundary.

## 5. Implement at your pace

- **Minimum:** finish an evidence-backed decision record with a concrete implementation plan
  and rollback point.
- **Target:** implement one bounded refinement, trace it, and keep the primary workflow green.
- **Stretch:** compare the same quality, cost, latency, or complexity measure before/after.

Do not combine several tracks.

## 6. Update the architecture

Create a before/after view or update the current diagram. Highlight exactly one changed
responsibility, component, or boundary. Preserve unchanged parts visually.

## 7. Rerun and interpret

Rerun:

- the representative path;
- relevant regression checks;
- the original measure.

Report supported, unsupported, or inconclusive. A useful negative result is acceptable when
the hypothesis and comparison were honest.

## Troubleshooting

**“I want to refactor everything first.”**
- Name the evidence and smallest seam that can test the hypothesis. Backlog unrelated cleanup.

**“The feedback suggested multi-agent.”**
- Feedback is not sufficient. Apply the separability, specialization/parallelism/routing, and
  measurable-benefit gates.

**“The new architecture works, but I did not save a baseline.”**
- You cannot claim improvement. Restore or check out the prior green commit in a safe branch,
  capture the baseline, then compare.

**“The measure improved, but an old eval is red.”**
- Report the regression. Decide whether the trade-off supports, rejects, or changes the
  hypothesis.

**“The diagram changed completely.”**
- The scope is probably too broad. Mark the one responsibility that evidence required and
  preserve the rest.

**“The result did not improve.”**
- Record the negative result and what it rules out. Do not silently add more changes.

**“I chose cost/latency but the runs vary.”**
- Use the same input, environment, model settings, and enough repetitions to make the
  comparison meaningful. Report variability.
