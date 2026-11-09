# Deployment Record

**Project / repository:** _…_  
**Owner:** _…_  
**Date:** _…_  
**Source commit:** _…_  
**Artifact / image / package version:** _…_

## 1. Release status

- **Result:** Live / Approved sandbox / Production-like fallback / Blocked
- **Deployment path:** Container / VM / Serverless / Managed app / Approved sandbox / Local production-like
- **Target environment:** _…_
- **Endpoint or invocation:** _redact private details as needed_
- **Release timestamp:** _…_
- **Primary platform selected because:** _…_
- **Fallback path:** _…_
- **Infrastructure blocker, if any:** _…_
- **Next action and owner:** _…_

> Nuvepro, if used, was confirmed available rather than assumed: Yes / No / Not used

## 2. Deployment contract

### Configuration and secrets

| Name | Config or secret? | Required? | Source / injection method | Safe default? | Missing-value behavior |
| --- | --- | --- | --- | --- | --- |
| _…_ | Config / Secret | Yes / No | _env, secret store, mounted file, etc._ | _…_ | _…_ |
| _…_ | _…_ | _…_ | _…_ | _…_ | _…_ |

- **Secrets excluded from source, artifacts, logs, and evidence:** Yes / No
- **Configuration version or safe checksum:** _…_
- **Rotation/revocation note:** _…_

Do not place secret values in this record.

### Health and readiness

| Signal | Route / command / observation | What it proves | Dependencies included | Expected result |
| --- | --- | --- | --- | --- |
| Health / liveness | _…_ | _…_ | _…_ | _…_ |
| Readiness | _…_ | _…_ | _…_ | _…_ |

- **Startup/grace period:** _…_
- **Failure behavior:** _restart, remove from traffic, return unavailable, etc._

### Persistence

- **State model:** Stateless / Persistent / Mixed
- **System(s) of record:** _…_
- **Data that must survive restart/redeploy:** _…_
- **Durable storage location:** _…_
- **Initialization or migration procedure:** _…_
- **Backward/forward compatibility:** _…_
- **Backup/restore or recovery expectation:** _…_
- **Restart/redeploy persistence test:** _…_

### External APIs and quotas

| Dependency / limit | Purpose | Timeout | Retry / idempotency | Failure behavior | Quota / budget / concurrency |
| --- | --- | --- | --- | --- | --- |
| _…_ | _…_ | _…_ | _…_ | _…_ | _…_ |
| _…_ | _…_ | _…_ | _…_ | _…_ | _…_ |

- **Retry-storm protection:** _…_
- **Usage/spend guard:** _…_
- **Degraded or unavailable mode:** _…_

## 3. Reproducibility

- **Runtime/toolchain versions:** _…_
- **Dependency lock or resolved-version artifact:** _…_
- **Build command:** `…`
- **Release/run command or procedure:** `…`
- **Verification command:** `…`
- **Artifact provenance:** _how the artifact maps to the source commit_
- **Required platform assumptions:** _…_
- **Clean-environment reproduction result:** Pass / Partial / Fail — _evidence_

## 4. Preflight result

- **Checklist location:** _…_
- **Decision:** Go / Conditional go / Fallback / No-go
- **Failed or waived gates:** _…_
- **Risk, owner, and expiry for each accepted exception:** _…_
- **Known-good rollback version:** _…_

## 5. Release log

| Time | Step / command | Result | Evidence / run ID |
| --- | --- | --- | --- |
| _…_ | Build | Pass / Fail | _…_ |
| _…_ | Release / start | Pass / Fail | _…_ |
| _…_ | Health | Pass / Fail | _…_ |
| _…_ | Readiness | Pass / Fail | _…_ |

## 6. Production smoke test

- **Test name / case ID:** _…_
- **Why this represents the primary workflow:** _…_
- **Sanitized request / input:** _…_
- **Expected result / side effect:** _…_
- **Actual result / side effect:** _…_
- **Status and latency:** _…_
- **Persistence check, if relevant:** _…_
- **Relevant log / trace ID:** _…_
- **Unhandled error or secret-leak check:** Pass / Fail
- **Overall smoke result:** Pass / Fail / Partial

## 7. Rollback or recovery

- **Rollback trigger:** _…_
- **Procedure / command:** `…`
- **Configuration rollback:** _…_
- **Schema/data compatibility constraint:** _…_
- **Recovery verification:** _health + readiness + smoke test_
- **Mode:** Demonstrated / Rehearsed locally / Tabletop only / Not completed
- **Outcome and elapsed time:** _…_
- **Untested assumptions:** _…_

## 8. Evidence index

| Evidence | Location / identifier | Sanitized? | What it proves |
| --- | --- | --- | --- |
| Source + artifact identity | _…_ | Yes / No | _…_ |
| Build/release output | _…_ | Yes / No | _…_ |
| Health/readiness | _…_ | Yes / No | _…_ |
| Smoke test | _…_ | Yes / No | _…_ |
| Persistence/restart | _…_ | Yes / No / N/A | _…_ |
| Rollback/recovery | _…_ | Yes / No | _…_ |

## 9. Conclusion

- [ ] live endpoint retained
- [ ] approved sandbox retained
- [ ] production-like fallback completed
- [ ] release rolled back
- [ ] release remains blocked

**What today's evidence proves:** _…_

**What it does not prove:** _…_

**Known production limitations:** _…_

**Next action, owner, and acceptance test:** _…_
