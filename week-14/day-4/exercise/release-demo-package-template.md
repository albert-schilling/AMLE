# Release and Demo Package

**Project / repository:** _…_  
**Release commit / tag:** _…_  
**Package owner:** _…_  
**Prepared / verified date:** _…_  
**Target environment:** _…_

## 1. Release identity

- **Primary user and problem:** _…_
- **Primary workflow:** _…_
- **Release status:** Candidate / Verified / Blocked
- **Artifact or deployment URL:** _…_
- **Versioned config/model/prompt identifiers:** _…_
- **Integrity reference (optional):** _tag, digest, checksum, artifact ID_

## 2. Stranger-runnable README

- **README path / URL:** _…_
- **Verification environment:** _fresh clone, clean venv, container, alternate machine, etc._
- **Verifier:** Self-reset / Peer / Other
- **Exact path attempted:** _setup → configure → run → test/eval → deploy/verify_
- **First ambiguity or failure:** _…_
- **Correction made:** _…_
- **Final outcome:** Pass / Partial / Blocked
- **Evidence:** _log, command output, deployment health result, or reviewer note_

### Required coverage

- [ ] purpose, intended user, and primary workflow
- [ ] prerequisites and exact setup
- [ ] configuration names, safe defaults, and secret sources
- [ ] exact run command and success signal
- [ ] exact test/eval command and result interpretation
- [ ] exact deploy and post-deploy verification path, or honest status
- [ ] architecture as built and important boundaries
- [ ] evaluation method, version, results, and links
- [ ] safety controls, residual risks, and escalation
- [ ] known limitations and unsupported use

## 3. Demo story

**Audience:** _…_  
**Time budget:** _…_  
**Demo release/environment:** _…_

| Beat | Claim | Action / artifact | Evidence shown | Time |
| --- | --- | --- | --- | --- |
| Problem | _…_ | _…_ | _…_ | _…_ |
| Representative input | _…_ | _…_ | _…_ | _…_ |
| Decision / action | _…_ | _…_ | _…_ | _…_ |
| Outcome | _…_ | _…_ | _…_ | _…_ |
| Eval / safety / operations | _…_ | _…_ | _…_ | _…_ |
| Limitation and close | _…_ | _…_ | _…_ | _…_ |

**One-sentence takeaway:** _…_

## 4. Fragile dependency fallback ladder

| Dependency | Failure signal | Live path | Safe retry/reset | Captured evidence | Static/local fallback | Switch cue |
| --- | --- | --- | --- | --- | --- | --- |
| _…_ | _…_ | _…_ | _…_ | _path + version/date_ | _…_ | _…_ |

**Fallback provenance check:** _How does each fallback prove the same claim for this release?_

## 5. Rubric evidence map

Every row uses the four-part evidence contract: claim, artifact, pointer, and limit.

| Criterion | Claim | Artifact | Pointer | Limit | Status |
| --- | --- | --- | --- | --- | --- |
| **B1 — Works end-to-end** | _…_ | _real input run, commit, environment_ | _exact section, run ID, or timestamp_ | _what it does not prove_ | Proven / Partial / Missing |
| **B2 — Evaluated** | _…_ | _golden set, measured metrics_ | _result file, suite version, row IDs_ | _what it does not prove_ | Proven / Partial / Missing |
| **B3 — Grounded & correct** | _…_ | _correctness and citation/grounding evidence_ | _exact case, output, or source link_ | _what it does not prove_ | Proven / Partial / Missing / N/A |
| **B4 — Sound architecture** | _…_ | _current diagram, boundaries, tests_ | _file, diagram, or decision record_ | _what it does not prove_ | Proven / Partial / Missing |
| **B5 — Observability** | _…_ | _trace showing what happened and why_ | _trace ID, dashboard, or log query_ | _what it does not prove_ | Proven / Partial / Missing |
| **B6 — Robustness & safety** | _…_ | _failure cases, controls, tests_ | _test path, run ID, residual-risk note_ | _what it does not prove_ | Proven / Partial / Missing |
| **B7 — Demo & docs** | _…_ | _README verification, demo, fallback_ | _README section, commit, or recording_ | _what it does not prove_ | Proven / Partial / Missing |

## 6. Final self-check

### Minimum

- [ ] Every required README section exists or states an honest status.
- [ ] One representative primary workflow fits the demo time.
- [ ] Every fragile live dependency has a usable fallback.
- [ ] Every rubric criterion has evidence or an explicit gap.

### Target

- [ ] A stranger or equivalent clean reset verified the primary path.
- [ ] Run, test/eval, and deploy/verify commands have expected success signals.
- [ ] Every demo claim points to current evidence.
- [ ] The full fallback ladder was rehearsed.

### Stretch

- [ ] Release and evidence are versioned and integrity-linked.
- [ ] An alternate/recovery path was verified.
- [ ] A peer timed both live and fallback rehearsals.
- [ ] No rubric criterion depends on narration alone.

## 7. Honest release statement

- **Ready to demonstrate:** _…_
- **Known limitations:** _…_
- **Unsupported use:** _…_
- **Residual safety/operational risk:** _…_
- **Blocking issue, owner, and next action:** _…_
- **Final package location:** _…_
