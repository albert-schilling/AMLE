# Architecture Refinement Record

**Project / repository:** _…_
**Current green commit:** _…_
**Date:** _…_

## 1. Evidence trigger

Select the strongest signal:

- [ ] trace bottleneck or failure
- [ ] eval result
- [ ] confirmed midterm feedback
- [ ] known risk
- [ ] observed complexity / coupling
- [ ] cost or latency measurement

**Artifact / link / identifier:** _…_

**What it shows:** _…_

**Why it matters now:** _impact, frequency, risk, or blocker_

## 2. Baseline

- **Representative input / path:** _…_
- **Current architecture behavior:** _…_
- **Measure and value:** _quality, cost, latency, complexity, failure rate, etc._
- **Relevant regression checks:** _…_
- **Baseline trace/eval identifier:** _…_

## 3. Refinement hypothesis

> Because **[evidence]**, changing **[responsibility / component / boundary]** should improve
> **[named measure]** without breaking **[primary workflow / regression guard]**.

_Completed hypothesis: …_

## 4. Selected refinement track

- [ ] simplify responsibilities or boundaries
- [ ] improve routing or workflow state
- [ ] improve context / retrieval quality
- [ ] reduce cost or latency
- [ ] strengthen tool contracts
- [ ] introduce one multi-agent decomposition

**Why this track fits the signal:** _…_

**Why the alternatives are not the first move:** _…_

### If multi-agent is selected

- **Separable responsibility:** _…_
- **Specialized context/tools, useful parallelism, or routing value:** _…_
- **Why a tool/function/current-loop step is insufficient:** _…_
- **One explicit handoff contract:** _input, output, failure_
- **Measurable benefit that must justify coordination cost:** _…_

## 5. Bounded change

- **Component/boundary changed:** _…_
- **Smallest implementation step:** _…_
- **Files/modules expected to change:** _…_
- **What must not change:** _…_
- **Rollback point:** _…_

## 6. Architecture update

- **Before diagram/link:** _…_
- **After diagram/link:** _…_
- **Highlighted responsibility or boundary delta:** _…_
- **Decision record updated at:** _…_

## 7. Result

- **Implementation status:** Planned / In progress / Implemented
- **Primary workflow status:** _…_
- **Regression status:** _…_
- **New trace/eval identifier:** _…_
- **Observed measure/value:** _…_
- **Delta from baseline:** _…_
- **Regressions or trade-offs:** _…_

## 8. Interpretation

- [ ] hypothesis supported
- [ ] hypothesis not supported
- [ ] evidence inconclusive
- [ ] implementation not yet complete

**What the result means:** _…_

**Exact next step:** _…_
