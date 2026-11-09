# Week 14 · Day 2 — Production Deployment

Today you package and release your capstone through a platform-neutral deployment contract.
Use a container, VM, serverless service, managed app platform, or approved sandbox.

Aim for a live endpoint where feasible. If credentials, billing, quotas, provisioning, or
platform availability would block completion, use a documented production-like
local/container/sandbox fallback. Nuvepro is optional/unconfirmed and is never required.

## Deliverables

- completed [Deployment Record](./deployment-record-template.md);
- completed [Deployment Preflight Checklist](./deployment-preflight-checklist.md);
- reproducible build and run/release commands;
- sanitized smoke-test, health/readiness, and rollback evidence;
- live endpoint where feasible, or documented production-like fallback.

## 1. Select the deployment path

Choose the smallest feasible path that can run the primary workflow:

- container on a host or container service;
- virtual machine or long-running process host;
- serverless function or service;
- managed application platform;
- approved sandbox;
- production-like local process/container fallback.

Record the primary path, fallback, constraints, owner, and timebox. Do not redesign the
application to imitate another learner's platform.

## 2. Write the common deployment contract

Describe the behavior every path must provide.

### Configuration and secrets

- List required configuration keys and safe defaults.
- List secret names and injection method, never values.
- Keep secrets out of source, images, artifacts, logs, and screenshots.
- Define startup behavior when required configuration is missing.

### Health and readiness

- **Health/liveness:** is the process alive and able to continue?
- **Readiness:** can it safely receive traffic and reach required dependencies?
- Document route, command, probe, or observable signal for each.

Do not make readiness depend on an optional third party unless the primary workflow does.

### Persistence

- State whether the service is stateless or persistent.
- Name the system of record and data that must survive restart/redeploy.
- Record initialization/migration, backup, and compatibility expectations where relevant.
- Do not rely on ephemeral disk for durable state.

### External APIs and quotas

- Record required APIs, timeouts, retries, and idempotency behavior.
- Define degraded behavior for API failure or malformed responses.
- Record rate, concurrency, token, compute, storage, or spend limits.
- Prevent retry storms and unbounded consumption.

### Reproducibility

- Pin dependencies or record resolved versions.
- Identify the source commit and artifact/image/version.
- Provide build, release/run, and verification commands.
- State runtime/toolchain versions and platform-specific assumptions.

## 3. Pass preflight

Complete the checklist before releasing. Any failed gate must be:

1. fixed;
2. accepted explicitly with impact and owner; or
3. routed to the fallback.

Never bypass a secret exposure, destructive migration, or unrecoverable-release blocker.

## 4. Release one exact version

Record:

- source commit;
- artifact/image/package identity;
- target environment;
- release timestamp;
- configuration version or safe checksum;
- exact release command or procedure.

For a fallback, use the production build and entrypoint where possible. Avoid hot reload,
embedded development secrets, and undocumented machine state.

## 5. Run the release smoke test

After release:

1. verify process health;
2. verify readiness and required dependencies;
3. run one representative primary-workflow request;
4. check expected output, side effect, or persisted state;
5. inspect logs/trace for unhandled errors and secret leakage;
6. record latency, status, and evidence location.

A homepage response alone does not prove the capstone workflow works.

## 6. Decide: keep, fix forward, or rollback

Define the rollback trigger before release. If the smoke test fails:

- stop routing traffic or stop the release;
- restore the prior known-good artifact/configuration;
- handle schema/data compatibility safely;
- rerun health, readiness, and smoke checks;
- record what happened.

If an actual rollback is unsafe or unavailable, perform a tabletop or local rehearsal and
state the untested assumptions.

## Pace bars

- **Minimum:** complete the contract and preflight; run the production artifact through a
  production-like local/container/sandbox smoke test; document blockers and rollback steps.
- **Target:** deploy a live endpoint or approved sandbox where feasible; pass health,
  readiness, and primary-workflow smoke checks; rehearse or demonstrate rollback; complete
  the Deployment Record.
- **Stretch:** automate release/smoke gates, rehearse migration or dependency failure,
  implement staged release, or measure recovery time.

## Evidence rules

Useful evidence includes:

- commit and artifact identifiers;
- sanitized command output;
- health/readiness responses;
- smoke-test request/result;
- relevant logs or trace IDs;
- persistence/restart result;
- rollback rehearsal/result.

Redact tokens, credentials, private URLs, personal data, and sensitive payloads. Prefer
durable text artifacts and links over screenshots alone.

## Troubleshooting

**“I do not have cloud credentials or billing.”**
- Record the blocker and switch to the production-like fallback. Infrastructure must not
  block the deliverable.

**“Nuvepro might be available.”**
- Use it only after access is confirmed. Keep the fallback ready and do not wait on it.

**“The platform does not expose separate health and readiness probes.”**
- Document equivalent commands or observable signals and explain their semantics.

**“My project is stateless.”**
- State that explicitly and identify any external systems that still own state.

**“The endpoint is live, so am I done?”**
- No. Run the representative smoke test and capture reproducibility, rollback, and evidence.

**“The deploy failed near the end of class.”**
- Preserve the failure evidence, timebox one diagnosis, then execute the fallback path and
  complete the Deployment Record.

**“Rollback could damage data.”**
- Do not perform an unsafe rollback. Rehearse the control path, document schema compatibility
  limits, and identify a safe forward-recovery or restore procedure.
