# Week 13 · Day 5 — Evaluation Iteration & Robustness Tuning

Today you expand the golden set, record a reproducible baseline, prioritize one failure,
make one intervention, and rerun the same suite.

## Deliverables

- completed [Eval Iteration Report](./eval-iteration-report-template.md);
- completed [Robustness Checklist](./robustness-checklist.md);
- expanded golden set and saved before/after results;
- prioritized Week 14 production-hardening backlog.

## 1. Add representative robustness cases

Choose cases based on real user behavior, traces, known risks, and architecture boundaries:

- edge / boundary values;
- adversarial or unsafe requests;
- dependency timeout or malformed result;
- irrelevant context or scope isolation;
- retry, duplicate action, or invalid state transition;
- missing, conflicting, or ambiguous information.

For each case, record expected behavior and relevant metric rung. Do not add random
paraphrases simply to increase row count.

## 2. Freeze the evaluation

Record:

- suite path/version/hash;
- baseline commit;
- model and parameters;
- prompt/config version;
- evaluator/judge version;
- thresholds;
- environment/dependency mode.

Do not change these after seeing the baseline.

## 3. Run the relevant metric ladder

Use only the rungs your workflow needs:

1. smoke / structural;
2. deterministic correctness;
3. grounding / retrieval;
4. judge quality;
5. outcome / task success.

Save per-rung and row-level results.

## 4. Prioritize one failure

Group failures by behavior or likely cause. Compare impact and frequency.

- high impact + frequent → usually fix first;
- high impact + rare → investigate, especially safety/privacy/irreversible actions;
- low impact + frequent → watch or tune later;
- low impact + rare → backlog.

State why the selected category outranks the others.

## 5. Make one intervention

Write the hypothesis first:

> Because **[failure evidence / cause]**, changing **[one behavior]** should improve
> **[metric / cases]** without regressing **[guards]**.

Implement only that bounded change.

## 6. Rerun the same suite

Use the same cases, settings, thresholds, and evaluators. Report:

- target metric delta;
- row-level improvements;
- unchanged failures;
- regressions;
- cost/latency movement where relevant;
- uncertainty or variability.

A useful negative result is valid evidence. Do not stack another intervention before
interpreting it.

## Pace bars

- **Minimum:** reproducible baseline, one prioritized failure, and a stated hypothesis.
- **Target:** targeted intervention rerun against the same suite, producing a documented
  improvement or useful negative result.
- **Stretch:** robustness slice, regression gate, or cost/latency comparison with trade-offs.

## 7. Prepare Week 14

Turn unresolved failures into a prioritized production-hardening backlog:

- Monday: safety hardening;
- Tuesday: deployment;
- Wednesday: observability polish;
- Thursday: documentation and demo preparation;
- Friday: graduation presentation.

Each backlog item needs evidence and an acceptance test.

## Troubleshooting

**“My intervention reached the final threshold already.”**
- Good, but still report the baseline, delta, and regressions. The method matters.

**“The metric improved only because I removed hard cases.”**
- Restore the frozen suite. That is not improvement.

**“Judge scores vary.”**
- Freeze judge prompt/model, repeat runs, report distribution or uncertainty, and retain
  cheap deterministic guards.

**“Aggregate score improved, but one row regressed.”**
- Report it. Evaluate impact; do not hide the row inside the average.

**“Nothing improved.”**
- Mark a useful negative result if the comparison was valid. Explain what it rules out and
  write the next hypothesis.

**“I do not have time to rerun everything.”**
- Reduce intervention scope. An implementation without the rerun does not establish effect.

**“I keep adding test cases.”**
- Stop once distinct risks are represented. Baseline the frozen suite and complete one loop.
