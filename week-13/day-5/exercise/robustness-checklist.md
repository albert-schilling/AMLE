# Evaluation Iteration & Robustness — Acceptance Checklist

## Golden-set expansion

- [ ] New cases represent real users, traces, risks, or architecture boundaries.
- [ ] Each case has an explicit expected behavior.
- [ ] Each case is labelled: edge, adversarial, dependency, context, state, or ambiguity.
- [ ] Safety/refusal/escalation behavior is specified where relevant.
- [ ] Cases add distinct risk coverage, not random paraphrases.

## Minimum — reproducible baseline

- [ ] Suite version/hash and baseline commit are recorded.
- [ ] Model, prompt/config, evaluator, thresholds, and environment are recorded.
- [ ] Relevant metric-ladder rungs have baseline results.
- [ ] One failure category is prioritized by impact and frequency.
- [ ] A targeted intervention hypothesis is stated.
- [ ] Guard cases/metrics are named.

## Target — complete one iteration

- [ ] One bounded intervention was implemented.
- [ ] Suite, settings, thresholds, and evaluators remained unchanged.
- [ ] The full relevant suite was rerun.
- [ ] Target delta and row-level changes are reported.
- [ ] Regressions and trade-offs remain visible.
- [ ] The result is interpreted as improvement, negative, inconclusive, or regressive.

## Stretch — deepen evidence

Choose one:

- [ ] Add a distinct robustness slice.
- [ ] Add a deterministic regression gate.
- [ ] Compare cost or latency under matched conditions.
- [ ] Repeat variable runs and report uncertainty.

## Week 14 handoff

- [ ] Updated scope and functionally complete primary workflow are linked.
- [ ] Expanded eval suite and iteration report are linked.
- [ ] Updated architecture, context decision, and midterm feedback are linked.
- [ ] Production-hardening backlog is prioritized.
- [ ] Every backlog item includes evidence and an acceptance test.

> Today requires a defensible delta from baseline—not attainment of the final ship threshold.
