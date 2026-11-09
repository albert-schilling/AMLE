# Evidence-Led Demo Runbook

**Project / release:** _…_  
**Audience:** _…_  
**Total time budget:** _…_  
**Demo environment:** _…_  
**Operator:** _…_

## 1. Demo contract

- **User problem:** _…_
- **Representative workflow:** _…_
- **Three claims at most:** _…_
- **One-sentence takeaway:** _…_
- **Known limitation to state:** _…_
- **What is intentionally out of scope:** _…_

## 2. Preflight

- [ ] Release commit/tag and configuration match the package.
- [ ] Primary workflow smoke check passes.
- [ ] Demo input is valid, representative, and safe to show.
- [ ] Accounts, permissions, quotas, and network are checked.
- [ ] Logs/traces/eval artifacts are open at exact locations.
- [ ] Notifications, private data, and secret-bearing output are hidden.
- [ ] Fallback artifacts are current, legible, and version-labeled.
- [ ] Timer and stop points are known.

## 3. Timed evidence story

| Time | Beat | Exact words / action | Claim | Evidence and observation | Stop rule |
| --- | --- | --- | --- | --- | --- |
| _…_ | Problem | _…_ | _…_ | _…_ | _…_ |
| _…_ | Input | _…_ | _…_ | _…_ | _…_ |
| _…_ | Decision/action | _…_ | _…_ | _…_ | _…_ |
| _…_ | Outcome | _…_ | _…_ | _…_ | _…_ |
| _…_ | Eval/safety/operations | _…_ | _…_ | _…_ | _…_ |
| _…_ | Limitation/close | _…_ | _…_ | _…_ | _…_ |

## 4. Claim-to-evidence check

| Claim | Primary evidence | Backup evidence | Release/version match? | What it does not prove |
| --- | --- | --- | --- | --- |
| _…_ | _…_ | _…_ | Yes / No | _…_ |

Remove or narrow any claim without evidence.

## 5. Fallback ladder

| Fragile dependency | Detect failure when… | Attempt once | Switch after… | Fallback artifact | Transition sentence |
| --- | --- | --- | --- | --- | --- |
| _…_ | _…_ | _bounded retry/reset_ | _time/condition_ | _path + capture date/version_ | _…_ |

Fallback order:

1. live path;
2. one bounded safe retry or reset;
3. captured trace/log/screenshot/recording from the same release;
4. static/local artifact that preserves the claim;
5. state the unresolved failure and continue.

Never fabricate a result, loop on retries, or present stale evidence as live.

## 6. Recovery cues

- **Live path succeeds:** “_…_”
- **Switching to captured evidence:** “The live dependency is unavailable; this versioned
  artifact shows the same release completing the step.”
- **Evidence is partial:** “_…_”
- **Claim cannot be demonstrated:** “_…_”
- **Returning to the story:** “_…_”

## 7. Rehearsal log

| Run | Mode | Duration | Failure/ambiguity | Change made | Result |
| --- | --- | --- | --- | --- | --- |
| 1 | Live | _…_ | _…_ | _…_ | _…_ |
| 2 | Forced fallback | _…_ | _…_ | _…_ | _…_ |
| 3 | Peer timed | _…_ | _…_ | _…_ | _…_ |

## 8. Final go/no-go

- [ ] Story fits the time budget without rushing.
- [ ] Every important claim has visible evidence.
- [ ] The primary path starts from a known state.
- [ ] Every fragile dependency has a rehearsed switch condition.
- [ ] Fallback evidence proves the same claim for the same release.
- [ ] Limitation and uncertainty language is explicit.
- [ ] Backup details are available without cluttering the main story.
