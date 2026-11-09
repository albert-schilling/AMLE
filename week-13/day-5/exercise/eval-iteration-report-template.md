# Eval Iteration Report

**Project / repository:** _…_
**Baseline commit:** _…_
**Intervention commit:** _…_
**Date:** _…_

## 1. Reproducibility metadata

- **Suite path + version/hash:** _…_
- **Model + version:** _…_
- **Model parameters:** _temperature, seed if available, etc._
- **Prompt/config version:** _…_
- **Evaluator / judge version:** _…_
- **Environment / dependency mode:** _…_
- **Number of repetitions (if relevant):** _…_

## 2. Expanded golden set

| Case ID | Category | Source / rationale | Input summary | Expected behavior | Relevant rung(s) |
| --- | --- | --- | --- | --- | --- |
| _…_ | Happy / Edge / Adversarial / Dependency / Context / State / Ambiguity | _…_ | _…_ | _…_ | 1 / 2 / 3 / 4 / 5 |
| _…_ | _…_ | _…_ | _…_ | _…_ | _…_ |
| _…_ | _…_ | _…_ | _…_ | _…_ | _…_ |

## 3. Baseline results

| Metric rung | Metric / check | Threshold | Baseline result | Pass? |
| --- | --- | --- | --- | --- |
| 1. Smoke / structural | _…_ | _…_ | _…_ | _…_ |
| 2. Deterministic correctness | _…_ | _…_ | _…_ | _…_ |
| 3. Grounding / retrieval | _…_ | _…_ | _…_ | _…_ |
| 4. Judge quality | _…_ | _…_ | _…_ | _…_ |
| 5. Outcome / task success | _…_ | _…_ | _…_ | _…_ |

**Baseline artifact / output path:** _…_

## 4. Prioritized failure

- **Failure category:** _…_
- **Affected case IDs:** _…_
- **Impact:** Low / Medium / High — _why_
- **Frequency:** Low / Medium / High — _evidence or estimate_
- **Likely cause:** _…_
- **Why this failure is first:** _…_
- **Other failures kept as guards/backlog:** _…_

## 5. Intervention hypothesis

> Because **[failure evidence / likely cause]**, changing **[one bounded behavior]** should
> improve **[metric and target cases]** without regressing **[guard metrics/cases]**.

_Completed hypothesis: …_

## 6. Targeted intervention

- **Change made:** _…_
- **Files/components changed:** _…_
- **What deliberately did not change:** _suite, threshold, settings, unrelated behavior_
- **Trace/run identifier:** _…_

## 7. Same-suite rerun

| Metric rung | Baseline | Rerun | Delta | Threshold | Regression / trade-off |
| --- | --- | --- | --- | --- | --- |
| 1. Smoke / structural | _…_ | _…_ | _…_ | _…_ | _…_ |
| 2. Deterministic correctness | _…_ | _…_ | _…_ | _…_ | _…_ |
| 3. Grounding / retrieval | _…_ | _…_ | _…_ | _…_ | _…_ |
| 4. Judge quality | _…_ | _…_ | _…_ | _…_ | _…_ |
| 5. Outcome / task success | _…_ | _…_ | _…_ | _…_ | _…_ |

### Row-level changes

| Case ID | Baseline | Rerun | Changed? | Interpretation |
| --- | --- | --- | --- | --- |
| _…_ | _…_ | _…_ | Improved / Regressed / Same | _…_ |
| _…_ | _…_ | _…_ | _…_ | _…_ |
| _…_ | _…_ | _…_ | _…_ | _…_ |

## 8. Conclusion

- [ ] measurable improvement
- [ ] useful negative result
- [ ] inconclusive / more repetitions needed
- [ ] improvement with material regression

**What the iteration proved:** _…_

**What it did not prove:** _…_

**Next hypothesis:** _…_

## 9. Week 14 production-hardening backlog

| Priority | Risk / failure | Evidence | Week 14 focus | Acceptance test |
| --- | --- | --- | --- | --- |
| 1 | _…_ | _…_ | Safety / Deployment / Observability / Docs+Demo / Graduation | _…_ |
| 2 | _…_ | _…_ | _…_ | _…_ |
| 3 | _…_ | _…_ | _…_ | _…_ |
