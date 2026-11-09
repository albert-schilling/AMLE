# Production Deployment — Preflight Checklist

Use this checklist for any container, VM, serverless service, managed app platform, approved
sandbox, or production-like fallback. Mark non-applicable items `N/A` and explain why.

## Path and scope

- [ ] The target and fallback paths are named.
- [ ] Platform access, credentials, billing, region, and required services are confirmed.
- [ ] Nuvepro is treated as optional/unconfirmed unless access is already verified.
- [ ] A timebox for infrastructure diagnosis is set.
- [ ] The exact primary workflow to smoke test is named.
- [ ] The release owner and rollback decision-maker are named.

## Configuration and secrets

- [ ] Required configuration keys are inventoried.
- [ ] Required secrets are inventoried by name only.
- [ ] Secrets are injected outside source code and build artifacts.
- [ ] Secrets do not appear in logs, screenshots, command history, or submitted evidence.
- [ ] Missing required values fail safely with an actionable message.
- [ ] Environment-specific values are not hard-coded.
- [ ] Rotation or revocation is possible without rebuilding application code.

## Health and readiness

- [ ] A health/liveness signal proves the process can continue.
- [ ] A readiness signal proves the service can handle the primary workflow.
- [ ] Required dependencies are represented in readiness where appropriate.
- [ ] Optional dependencies do not incorrectly block readiness.
- [ ] Startup/grace timing and failure behavior are documented.
- [ ] Probes avoid destructive, costly, or quota-heavy operations.

## Persistence and change safety

- [ ] The service is declared stateless, persistent, or mixed.
- [ ] Durable state has an explicit system of record.
- [ ] Required state does not rely on ephemeral filesystem storage.
- [ ] Initialization and migration steps are documented and repeatable.
- [ ] Schema/data compatibility with the previous version is understood.
- [ ] Backup, restore, or forward-recovery expectations are recorded.
- [ ] Destructive operations require explicit review and recovery evidence.

## External APIs and quotas

- [ ] Required external dependencies and credentials are confirmed.
- [ ] Calls have explicit timeouts.
- [ ] Retries are bounded and use backoff where appropriate.
- [ ] Repeated side effects are idempotent or otherwise protected.
- [ ] Malformed, unavailable, and rate-limited responses fail safely.
- [ ] Rate, concurrency, token, compute, storage, and spend limits are known.
- [ ] Usage or spend has a guard, alert, cap, or documented manual control.
- [ ] The system avoids retry storms and uncontrolled fan-out.

## Reproducibility

- [ ] The source commit is recorded and working tree state is understood.
- [ ] Runtime/toolchain versions are recorded.
- [ ] Dependencies are locked or resolved versions are captured.
- [ ] Build command succeeds from a clean-enough environment.
- [ ] Artifact/image/package identity maps to the source commit.
- [ ] Release/run and verification commands are recorded.
- [ ] The production entrypoint does not depend on hot reload or local IDE state.

## Release and rollback

- [ ] The previous known-good version is identified.
- [ ] The rollback trigger is defined before release.
- [ ] Rollback/recovery commands and permissions are available.
- [ ] Configuration can be restored with the application version.
- [ ] Persistence changes do not make rollback unsafe.
- [ ] Failed releases can be removed from traffic or stopped.
- [ ] Rollback will be followed by health, readiness, and smoke checks.

## Smoke test and evidence

- [ ] A sanitized representative request/input is prepared.
- [ ] Expected output, side effect, or state change is explicit.
- [ ] Health and readiness checks are prepared.
- [ ] Relevant logs/traces can be inspected without exposing secrets.
- [ ] Evidence locations and run identifiers are planned.
- [ ] Private URLs, credentials, personal data, and sensitive payloads will be redacted.

## Go / no-go decision

- [ ] No secret exposure remains.
- [ ] No destructive or unrecoverable migration blocker remains.
- [ ] Critical dependencies and quotas support the smoke test.
- [ ] A known-good version or safe recovery path exists.
- [ ] The chosen path can complete within the timebox.

**Decision:** Go / Conditional go / Fallback / No-go

**Failed or accepted gates, impact, owner, and expiry:** _…_

## Pace-aware completion

### Minimum

- [ ] Common deployment contract is complete.
- [ ] Preflight decision and blockers are recorded.
- [ ] Production artifact/entrypoint runs in a production-like fallback.
- [ ] Health/readiness and primary-workflow smoke evidence are captured.
- [ ] Rollback steps and untested assumptions are documented.

### Target

- [ ] Live endpoint or approved sandbox is released where feasible.
- [ ] Health, readiness, and representative smoke checks pass.
- [ ] Persistence/dependency behavior is verified where relevant.
- [ ] Rollback is demonstrated or rehearsed.
- [ ] Deployment Record and sanitized evidence index are complete.

### Stretch

Choose one:

- [ ] Automate build/release or environment provisioning.
- [ ] Add an automated post-release smoke gate.
- [ ] Rehearse staged/canary release or persistence migration.
- [ ] Test quota, timeout, or dependency-failure behavior.
- [ ] Measure rollback/recovery time.
