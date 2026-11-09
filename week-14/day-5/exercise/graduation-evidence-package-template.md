# Graduation Evidence Package

**Learner / team:** _…_  
**Project:** _…_  
**Repository:** _…_  
**Graduation commit:** _…_  
**Presentation:** _…_  
**Package date:** _…_

## 1. Executive summary

- **Intended user:** _…_
- **Problem / workflow:** _…_
- **Bounded success condition:** _…_
- **Current readiness claim:** _Use precise language supported by this package._
- **Primary limitation:** _…_
- **Highest-priority next step:** _…_

## 2. Scope and user evidence

| Item | Statement | Evidence link / ID | Limitation |
| --- | --- | --- | --- |
| Intended user and need | _…_ | _…_ | _…_ |
| In-scope outcome | _…_ | _…_ | _…_ |
| Non-goal / boundary | _…_ | _…_ | _…_ |
| Success measure | _…_ | _…_ | _…_ |

## 3. Architecture

**Architecture diagram:** _…_  
**Architecture decision record(s):** _…_

Describe the end-to-end flow:

1. **Input / entry point:** _…_
2. **Context, retrieval, or state:** _…_
3. **Model / agent / workflow decision:** _…_
4. **Tool or dependency interaction:** _…_
5. **Output / action / handoff:** _…_
6. **Observability and escalation:** _…_

### Key decisions and trade-offs

| Decision | Constraint / rationale | Alternative considered | Trade-off accepted | Evidence |
| --- | --- | --- | --- | --- |
| _…_ | _…_ | _…_ | _…_ | _…_ |
| _…_ | _…_ | _…_ | _…_ | _…_ |

## 4. Working end-to-end path

- **Representative scenario:** _…_
- **Expected outcome:** _…_
- **Run / trace ID:** _…_
- **Commit:** _…_
- **Environment:** _…_
- **Model/config versions:** _…_
- **External dependency mode:** _live / sandbox / mocked / mixed_
- **Observed result:** _…_
- **Live-demo fallback artifact:** _…_
- **What this run does not prove:** _…_

### Path checkpoints

| Checkpoint | Expected behavior | Observed evidence | Status |
| --- | --- | --- | --- |
| Input accepted | _…_ | _…_ | Pass / Partial / Fail |
| Decision/context assembled | _…_ | _…_ | Pass / Partial / Fail |
| Tool/dependency handled | _…_ | _…_ | Pass / Partial / Fail |
| User-visible outcome | _…_ | _…_ | Pass / Partial / Fail |
| Trace/telemetry captured | _…_ | _…_ | Pass / Partial / Fail |

## 5. Evidence index

Every row must include a bounded claim and its limit. Add or remove rows to fit the project.

| ID | Evidence area | Bounded claim | Artifact / link | Version / run | Limit / unknown |
| --- | --- | --- | --- | --- | --- |
| TR-01 | Trace | _…_ | _…_ | _…_ | _…_ |
| EV-01 | Evaluation | _…_ | _…_ | _…_ | _…_ |
| SF-01 | Safety | _…_ | _…_ | _…_ | _…_ |
| DP-01 | Deployment | _…_ | _…_ | _…_ | _…_ |
| OB-01 | Observability | _…_ | _…_ | _…_ | _…_ |
| UX-01 | User/problem | _…_ | _…_ | _…_ | _…_ |

## 6. Trace evidence

- **Representative trace(s):** _…_
- **Correlation/run identifiers:** _…_
- **Inputs/outputs redacted appropriately:** Yes / No / N/A
- **Key decision or state transition visible:** _…_
- **Failure/escalation path visible:** _…_
- **Trace limitation:** _…_

## 7. Evaluation evidence

- **Suite path + version/hash:** _…_
- **Evaluation commit/config:** _…_
- **Cases and relevant metric rungs:** _…_
- **Thresholds set before the run:** _…_
- **Latest result:** _…_
- **Row-level result artifact:** _…_
- **Known regressions / uncertainty:** _…_
- **Evaluation limitation:** _…_

## 8. Safety evidence

| Risk / misuse | Expected control | Test or review | Result | Residual risk |
| --- | --- | --- | --- | --- |
| _…_ | _…_ | _…_ | Pass / Partial / Fail / Not tested | _…_ |
| _…_ | _…_ | _…_ | _…_ | _…_ |

- **Human approval / escalation boundary:** _…_
- **Data, secret, or privacy handling evidence:** _…_
- **Safety limitation:** _…_

Do not claim the system is “safe” solely because a guardrail exists. Report tested behavior
and residual risk.

## 9. Deployment evidence

- **Environment / URL or endpoint:** _…_
- **Deployment version / commit:** _…_
- **Configuration and secret handling:** _…_
- **Health check / smoke evidence:** _…_
- **Rollback or recovery evidence:** _…_
- **Access boundary:** _local / private / controlled pilot / public / other_
- **Observed availability window or test conditions:** _…_
- **Deployment limitation:** _…_

A reachable endpoint does not by itself establish production readiness.

## 10. Honest limitations and unknowns

| Limitation / unknown | Evidence showing the gap | User / system impact | Current mitigation |
| --- | --- | --- | --- |
| _…_ | _…_ | _…_ | _…_ |
| _…_ | _…_ | _…_ | _…_ |
| _…_ | _…_ | _…_ | _…_ |

## 11. Prioritized next steps

| Priority | Next step | Evidence-based reason | Acceptance test / new evidence |
| --- | --- | --- | --- |
| 1 | _…_ | _…_ | _…_ |
| 2 | _…_ | _…_ | _…_ |
| 3 | _…_ | _…_ | _…_ |

## 12. Reproduction and review

```text
Repository / artifact access:
Required runtime and versions:
Setup command:
Run command:
Evaluation command:
Expected output:
Known environment constraints:
```

### Final package check

- [ ] Links open with reviewer permissions.
- [ ] Graduation commit and artifact versions are recorded.
- [ ] No secrets, credentials, or inappropriate personal data are exposed.
- [ ] Claims identify the conditions under which they were observed.
- [ ] Failed, partial, and missing evidence remains visible.
- [ ] Limitations and next steps agree with the evidence.
- [ ] Final rubric ratings link back to package items.

## 13. Submission

**Submission location:** [SUBMISSION LOCATION]  
**Submitted artifact/link:** _…_  
**Submission timestamp:** _…_
