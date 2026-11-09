# Week 14 · Day 3 — Observability Polish

> **Half-day scope:** These materials cover only the capstone Observability Polish half.
> The standing Career Session is separate and is not authored here.

## Teacher-configured logistics

- Work block: `[WORK BLOCK MINUTES]` minutes
- Pair review: `[PAIR REVIEW MINUTES]` minutes
- Submission location: `[SUBMISSION LOCATION]`
- Observability access or fallback: `[OBSERVABILITY ACCESS / FALLBACK]`

## Deliverables

- completed [Observability Evidence Pack](./observability-evidence-pack-template.md);
- completed [Debug Runbook](./debug-runbook-template.md);
- links or redacted captures needed to inspect the selected run.

Do not submit secrets, access tokens, personal data, private prompts/context, raw user
payloads, or unrestricted model/tool responses.

## 1. Start with one operational question

Choose one recent representative run and one question such as:

- Where did this run spend its time?
- Which step first produced the wrong state or output?
- Did a retry, timeout, fallback, or external dependency affect the result?
- What usage or cost did this run incur, and where?
- Can an engineer locate all relevant evidence from one identifier?

Record the commit/version, environment, UTC time window, input class, expected outcome,
observed outcome, and run/correlation ID. Use a safe test case.

## 2. Diagnose before instrumenting

Follow the run using current evidence. At each meaningful boundary, record:

- component or operation;
- start/end or duration;
- status/outcome and error category;
- parent/child or causal relationship;
- tool/model/dependency name at a safe level;
- retry/fallback/cache behavior where relevant;
- safe attributes that explain the decision.

Mark evidence as **present**, **partial**, or **missing**. Do not add telemetry everywhere.
Choose the missing boundary that most blocks diagnosis.

## 3. Improve correlation and coverage

Implement one bounded improvement appropriate to your stack:

- propagate the run/correlation ID across a component or external-call boundary;
- add a missing span or structured lifecycle event;
- attach status, duration, retry count, or safe outcome metadata;
- connect the final outcome to the initiating run.

Rerun the same safe scenario when possible. Capture before/after evidence and state what is
now answerable. If implementation is blocked, document the exact insertion point, field
contract, and validation plan.

## 4. Check safe metadata

Use an allowlist. Prefer metadata such as:

- operation/component name and version;
- environment and deployment/commit identifier;
- run/correlation ID and parent ID;
- status, error category, retry count, and timeout flag;
- duration, token/usage count, estimated cost with currency;
- model/tool/dependency identifier;
- input/output size or category rather than content.

Exclude secrets, credentials, raw personal data, private prompt/context text, unrestricted
payloads, and identifiers that are not needed. Hashing does not automatically make sensitive
data safe; consider linkability and retention.

## 5. Interpret three signal families

For the selected run, capture available evidence for:

1. **Latency:** end-to-end duration and the slowest meaningful operation.
2. **Cost/usage:** tokens, requests, compute, or another stack-relevant proxy.
3. **Errors:** explicit failures plus timeouts, retries, fallbacks, invalid states, or
   quality failures that may not throw an exception.

Use units and context. “Slow,” “expensive,” and “many errors” are not findings without a
baseline, expectation, threshold, or comparison.

## 6. Decide whether a dashboard or alert is useful

Do not build one by default. Add it only if you can name:

- the recurring question;
- the owner who will look or respond;
- the decision or action it changes;
- the threshold/window and why it is defensible;
- the false-positive or noise risk;
- a safe validation method.

It is acceptable to record **not useful yet** and explain which baseline or operational
ownership is missing.

## 7. Write and test the debugging path

Complete the Debug Runbook. It should take a responder from symptom to:

1. locating the run;
2. verifying end-to-end correlation;
3. finding the first meaningful anomaly;
4. checking latency, cost/usage, and error context;
5. choosing a safe next action or escalation.

Ask a peer to follow it during `[PAIR REVIEW MINUTES]` without relying on your narration.
Record where they became blocked or had to guess.

## Progress lanes

### Minimum

- Complete the real-run record and coverage map.
- Identify one likely cause or precise next inspection step.
- Record safe-data exclusions.
- Write a concise debugging path.

### Target

- Propagate correlation across the primary path.
- Implement and verify one high-value coverage/metadata improvement.
- Interpret latency, cost/usage, and errors.
- Incorporate peer runbook feedback.

### Stretch

- Validate one justified alert/dashboard or explicitly test why it is noisy.
- Exercise the runbook on a known failure or safe fault injection.
- Measure a defensible before/after improvement in coverage or time-to-finding.

## Submission

Submit both completed templates and safe evidence links/captures to
`[SUBMISSION LOCATION]`.

## Troubleshooting

**“My stack has no tracing product.”**
- Use correlated structured logs or a local run record. Preserve ordering, operation names,
  status, duration, and causal IDs. The concepts matter more than the vendor.

**“I cannot reproduce the original failure.”**
- Diagnose the original real evidence, then rerun a representative safe case. Separate facts
  from hypotheses and state what evidence would confirm the cause.

**“I cannot modify instrumentation today.”**
- Complete the minimum lane and write an implementation-ready insertion point, schema,
  propagation path, and verification check.

**“My run has no single ID.”**
- That is a finding. Add or plan one generated at ingress and propagated without placing
  sensitive data inside the identifier.

**“There are no exceptions.”**
- Inspect quality failures, invalid states, fallback use, timeouts, retries, empty results,
  and cancelled work. Operational failure is broader than thrown errors.

**“I do not know an alert threshold.”**
- Do not invent one. Record the baseline/window needed and defer the alert.

