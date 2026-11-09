# Observability Evidence Pack

## Teacher-configured logistics

- **Work block:** `[WORK BLOCK MINUTES]` minutes
- **Pair review:** `[PAIR REVIEW MINUTES]` minutes
- **Submission location:** `[SUBMISSION LOCATION]`
- **Observability access / fallback:** `[OBSERVABILITY ACCESS / FALLBACK]`

## Learner and run details

- **Name / team:** _…_
- **Project / repository:** _…_
- **Commit, version, or deployment:** _…_
- **Environment:** _local / test / staging / other_
- **UTC time window:** _…_
- **Evidence access/link:** _…_
- **Redaction checked by:** _…_

---

## 1. Operational question

**Question this evidence should answer:** _…_

**Why this question matters now:** _…_

**Expected decision or action:** _…_

## 2. Selected real run

- **Run/correlation ID or equivalent locator:** _…_
- **Representative input class (not raw sensitive content):** _…_
- **Expected outcome:** _…_
- **Observed outcome:** _…_
- **Why this run is representative:** _…_
- **Known constraints or uncertainty:** _…_

## 3. End-to-end trace coverage map

Use **present**, **partial**, **missing**, or **not applicable**.

| Order | Component / operation | Parent or cause visible? | Start/end or duration? | Status/outcome? | Safe useful metadata? | Coverage | Evidence link |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 1 | _entry point_ | _…_ | _…_ | _…_ | _…_ | _…_ | _…_ |
| 2 | _…_ | _…_ | _…_ | _…_ | _…_ | _…_ | _…_ |
| 3 | _…_ | _…_ | _…_ | _…_ | _…_ | _…_ | _…_ |
| 4 | _final outcome_ | _…_ | _…_ | _…_ | _…_ | _…_ | _…_ |

**Highest-value missing or partial boundary:** _…_

**Why it blocks diagnosis:** _…_

## 4. Correlation/run-ID check

- [ ] ID is created or accepted at the entry boundary.
- [ ] ID appears in each relevant component.
- [ ] ID crosses async, queue, tool, model, or external-call boundaries where applicable.
- [ ] Parent/child or causal relationships can be reconstructed.
- [ ] Final outcome can be linked back to the initiating run.
- [ ] The ID itself contains no sensitive data.

**Break in continuity, if any:** _…_

**Evidence:** _…_

## 5. Safe observability data inventory

### Allowlisted metadata used

| Field | Example shape, not sensitive value | Question answered | Retention/access note |
| --- | --- | --- | --- |
| _run_id_ | _opaque identifier_ | _…_ | _…_ |
| _operation_ | _bounded name_ | _…_ | _…_ |
| _status / error_category_ | _bounded enum_ | _…_ | _…_ |
| _duration_ms_ | _number_ | _…_ | _…_ |
| _…_ | _…_ | _…_ | _…_ |

### Explicit exclusions or transformations

| Data not recorded or transformed | Risk | Control |
| --- | --- | --- |
| _secrets / credentials_ | _…_ | _exclude_ |
| _raw personal data_ | _…_ | _exclude, redact, aggregate, or tokenize_ |
| _private prompt/context or payload_ | _…_ | _…_ |
| _…_ | _…_ | _…_ |

**Access and retention concern still open:** _…_

## 6. Signal evidence

### Latency

- **End-to-end duration + unit:** _…_
- **Slowest meaningful operation:** _…_
- **Comparison/baseline/expectation:** _…_
- **Interpretation:** _…_

### Cost or usage

- **Measure + unit:** _tokens, calls, compute time, estimated currency, other_
- **Run total:** _…_
- **Largest contributor:** _…_
- **Estimation caveat:** _…_
- **Interpretation:** _…_

### Errors and degraded behavior

- **Explicit error count/category:** _…_
- **Timeouts/retries/fallbacks/cancellations:** _…_
- **Quality or invalid-state failure:** _…_
- **First meaningful anomaly:** _…_
- **Interpretation:** _…_

## 7. Diagnosis

**Facts visible in the evidence:**

- _…_
- _…_

**Hypothesis, clearly labeled:** _…_

**Likely root cause or precise next inspection step:** _…_

**Confidence and what could change it:** _…_

## 8. Before/after observability improvement

- **Gap selected:** _…_
- **Bounded change:** _…_
- **Why this change outranked other gaps:** _…_
- **Validation run ID:** _…_

| Check | Before | After |
| --- | --- | --- |
| Correlation continuity | _…_ | _…_ |
| Trace/event coverage | _…_ | _…_ |
| Useful safe metadata | _…_ | _…_ |
| Question now answerable | _…_ | _…_ |

**What this improvement does not prove:** _…_

## 9. Alert/dashboard decision

- **Decision:** _add now / revise existing / defer / not useful_
- **Recurring operational question:** _…_
- **Owner and response action:** _…_
- **Signal, threshold, and window:** _…_
- **Baseline/rationale:** _…_
- **Noise or false-positive risk:** _…_
- **Safe validation:** _…_

If deferred or not useful, **what must become true first?** _…_

## 10. Debugging path and peer check

- **Runbook:** [link or attached template](./debug-runbook-template.md)
- **Reviewer:** _…_
- **Could the reviewer locate the run?** _yes / no_
- **Could the reviewer identify the first anomaly or next check?** _yes / no_
- **Where did the reviewer guess or stall?** _…_
- **Runbook revision made:** _…_

## Progress lane completed

- [ ] **Minimum:** real run, coverage map, diagnosis/next check, safe-data exclusions, runbook.
- [ ] **Target:** end-to-end correlation, verified improvement, three signal families, peer revision.
- [ ] **Stretch:** justified alert/dashboard or noise test, failure exercise, measured improvement.

## Final evidence check

- [ ] Every claim points to evidence or is labeled as a hypothesis.
- [ ] One identifier or documented locator connects the run.
- [ ] Units, time window, version, and environment are present.
- [ ] Missing coverage is visible rather than hidden.
- [ ] No secret or sensitive data appears in the pack.
- [ ] The next operational action is explicit.

