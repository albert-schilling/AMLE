# Debug Runbook — From Symptom to Next Action

> Keep this path concise enough to use under pressure. Use tool-neutral language and link to
> project-specific queries or views. Never paste secrets or sensitive payloads into the runbook.

## Ownership and scope

- **Service/workflow:** _…_
- **Primary owner:** _…_
- **Escalation contact/path:** _…_
- **Last tested (UTC):** _…_
- **Tested by:** _…_
- **Applies to versions/environments:** _…_

## Trigger

**Observable symptom:** _…_

**User/system impact:** _…_

**Start this runbook when:** _threshold, event, report, or reproducible behavior_

**Do not use this runbook when:** _…_

## Safety first

- [ ] Use approved access and the least-privileged environment.
- [ ] Do not expose or copy credentials, personal data, private prompts/context, or raw payloads.
- [ ] Prefer IDs, categories, hashes approved for use, and redacted samples.
- [ ] Record UTC times, version/deployment, environment, and every mitigation attempted.
- [ ] Stop and escalate before destructive, irreversible, or privacy-sensitive actions.

## Debugging path

### 1. Bound the event

Collect:

- UTC time window: _…_
- environment and version/deployment: _…_
- symptom and expected behavior: _…_
- affected input/output category, not sensitive content: _…_

If the scope cannot be bounded, next action: _…_

### 2. Locate the initiating run

**Lookup location/query:** _…_

**Required locator:** _run/correlation ID, request ID, safe event key, or time + version_

**Found run ID:** _…_

If no run is found:

1. verify clock/time zone and environment;
2. verify entry-point telemetry exists;
3. check sampling, ingestion delay, or local fallback;
4. record the observability gap and escalate to _…_.

### 3. Verify correlation continuity

Follow the run from entry point to final outcome.

- [ ] Entry event/span is present.
- [ ] Parent/causal relationship remains visible.
- [ ] Async/tool/model/external calls are linked where relevant.
- [ ] Final status/outcome is linked to the same run.

**First missing boundary:** _…_

If correlation breaks, inspect next: _propagation header/context, queue message field,
task-local context, adapter, callback, or equivalent_

### 4. Find the first meaningful anomaly

Do not start with the loudest downstream symptom. Compare operations in causal order.

| Check | What to inspect | Finding |
| --- | --- | --- |
| Status/outcome | first non-success or unexpected state | _…_ |
| Timing | end-to-end and operation durations | _…_ |
| Retry/fallback | count, reason, resulting status | _…_ |
| Dependency | safe name/version/status | _…_ |
| State/context | category, size, version—not raw content | _…_ |
| Final quality | eval/assertion/outcome signal | _…_ |

**First meaningful anomaly:** _…_

### 5. Check signal context

- **Latency:** baseline/threshold, unit, slowest operation: _…_
- **Cost/usage:** measure, unit, largest contributor, estimate caveat: _…_
- **Errors/degradation:** category, frequency, retry/fallback/quality context: _…_

**Does this affect one run or a wider window?** _…_

### 6. Separate fact from hypothesis

**Confirmed facts:**

- _…_
- _…_

**Current hypothesis:** _…_

**Evidence that would confirm or reject it:** _…_

### 7. Choose the next safe action

- [ ] No mitigation; continue investigation.
- [ ] Retry/replay only if idempotency and side effects are understood.
- [ ] Use approved fallback or disable a bounded path.
- [ ] Roll back or change configuration through the project's approved process.
- [ ] Escalate with the evidence bundle below.

**Action, owner, and reason:** _…_

**Success/rollback check:** _…_

## Escalation evidence bundle

Provide:

- symptom, impact, UTC window, environment, and version;
- run/correlation ID;
- first meaningful anomaly and evidence link;
- latency, cost/usage, and error context;
- actions already attempted and outcomes;
- remaining hypothesis or explicit unknown.

Do not provide raw sensitive content.

## Resolution and follow-up

- **Resolution or current status:** _…_
- **Root cause (only if confirmed):** _…_
- **Observability gap discovered:** _…_
- **Follow-up owner/date:** _…_
- **Alert/dashboard decision:** _add / revise / defer / none, because …_
- **Runbook change needed:** _…_

## Cold-path validation

Ask someone unfamiliar with the incident to use this runbook.

- [ ] They located the run without verbal guidance.
- [ ] They followed correlation end to end or identified the exact break.
- [ ] They found the first anomaly or precise next check.
- [ ] They understood which action was safe.
- [ ] They did not need sensitive data.

**Where they stalled or guessed:** _…_

**Revision made:** _…_

