# Safety Hardening Record

**Project / repository:** _…_
**Date:** _…_
**Baseline commit:** _…_
**Hardened commit:** _…_
**Selected pace bar:** Minimum / Target / Stretch

## 1. Starting evidence

- **Week 13 hardening backlog:** _path/link_
- **Eval suite path + version/hash:** _…_
- **Baseline result artifact:** _…_
- **Model + parameters:** _…_
- **Prompt/config version:** _…_
- **Evaluator version:** _…_
- **Environment/dependency mode:** _…_
- **Tool/service identities in scope:** _…_

## 2. Scope and deployment assumptions

- **Workflow in scope:** _one sentence_
- **Users/actors in scope:** _…_
- **Assets to protect:** _data, actions, credentials, decisions, availability, reputation, etc._
- **External effects:** _…_
- **Explicitly out of scope today:** _…_
- **Assumptions:** _authentication, tenancy, network, providers, human operators, etc._

## 3. Actual trust boundaries

| Boundary ID | From → to | Data/control crossing | Who controls input? | Acting identity/credential | Current check | Asset at risk |
| --- | --- | --- | --- | --- | --- | --- |
| TB-1 | _…_ | _…_ | _…_ | _…_ | _…_ | _…_ |
| TB-2 | _…_ | _…_ | _…_ | _…_ | _…_ | _…_ |
| TB-3 | _…_ | _…_ | _…_ | _…_ | _…_ | _…_ |

**Diagram / trace link:** _…_

## 4. Candidate risks and priority

| Risk ID | Actor/action/boundary/asset | Evidence | Severity + reversibility | Likelihood/exposure | Current controls | Priority |
| --- | --- | --- | --- | --- | --- | --- |
| R-1 | _…_ | _…_ | _…_ | _…_ | _…_ | _…_ |
| R-2 | _…_ | _…_ | _…_ | _…_ | _…_ | _…_ |
| R-3 | _…_ | _…_ | _…_ | _…_ | _…_ | _…_ |

### Selected risk

> **[Actor/source]** can **[action]** across **[boundary]**, affecting **[asset]** and causing
> **[impact]**, because **[current weakness/evidence]**.

- **Selected risk ID:** _…_
- **Why it outranks the others:** _…_
- **Safe behavior:** _reject / constrain / redact / deny / approve / fail closed / other_
- **Risks retained as regression guards or backlog:** _…_

## 5. Defense-in-depth plan

Use only relevant layers.

| Layer | Enforcement boundary | Concrete control | Prevent / detect / contain | Failure or bypass addressed | Evidence to collect |
| --- | --- | --- | --- | --- | --- |
| Input validation | _…_ | _…_ | _…_ | _…_ | _…_ |
| Tool authorization / least privilege | _…_ | _…_ | _…_ | _…_ | _…_ |
| Output / schema control | _…_ | _…_ | _…_ | _…_ | _…_ |
| Human approval, if warranted | _…_ | _…_ | _…_ | _…_ | _…_ |

**Why these layers are proportionate:** _…_

**Human approval decision:** Required / Not required — _why; if required, who approves,
what they see, how approval binds to the action, and denial/timeout behavior_

## 6. Hardening hypothesis

> Because **[risk evidence]**, enforcing **[layers]** at **[boundaries]** should cause
> **[adversarial cases]** to **[safe behavior]** while **[regression guards]** remain green.

_Completed hypothesis: …_

## 7. Adversarial test plan

| Case ID | Boundary/risk | Attack or failure input | Expected safe behavior | Observable assertion |
| --- | --- | --- | --- | --- |
| ADV-1 | _…_ | _…_ | _…_ | _…_ |
| ADV-2 | _…_ | _…_ | _…_ | _…_ |
| ADV-3 | _…_ | _…_ | _…_ | _…_ |

**Regression guard suite:** _unchanged Week 13 suite/path/hash_

## 8. Implementation

- **Control(s) implemented:** _…_
- **Files/config/policies changed:** _…_
- **Permissions before → after:** _…_
- **What deliberately did not change:** _suite, thresholds, unrelated workflow, etc._
- **Trace/run/deployment identifier:** _…_

## 9. Results

### Adversarial slice

| Case ID | Baseline behavior | Hardened behavior | Pass? | Evidence |
| --- | --- | --- | --- | --- |
| ADV-1 | _…_ | _…_ | _…_ | _…_ |
| ADV-2 | _…_ | _…_ | _…_ | _…_ |
| ADV-3 | _…_ | _…_ | _…_ | _…_ |

### Existing regression suite

| Suite/rung/slice | Baseline | Hardened | Delta | Regression / trade-off |
| --- | --- | --- | --- | --- |
| _…_ | _…_ | _…_ | _…_ | _…_ |
| _…_ | _…_ | _…_ | _…_ | _…_ |

- **False positives / valid actions blocked:** _…_
- **Latency/cost change:** _…_
- **Uncertainty or variable behavior:** _…_
- **Result:** Reduced / Negative / Inconclusive / Regressive

## 10. Residual risk

- **What the evidence supports:** _bounded claim_
- **What it does not prove:** _…_
- **Known bypasses / untested paths:** _…_
- **Remaining severity and exposure:** _…_
- **Provider/operator/human assumptions:** _…_
- **Detection or monitoring needed:** _…_
- **Rollback / fail-safe behavior:** _…_
- **Next safety action + acceptance test:** _…_

## 11. Completion

- [ ] **Minimum:** scope/boundaries, one prioritized risk, defense plan, and adversarial test
  are complete.
- [ ] **Target:** controls are implemented; adversarial and regression suites ran; residual
  risk is recorded.
- [ ] **Stretch:** one deeper test or deterministic gate for the same risk is complete.
