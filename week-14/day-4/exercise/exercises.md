# Week 14 · Day 4 — Documentation & Demo Preparation

Today you make your capstone runnable and reviewable by someone who did not build it. Package
the release, write exact operating instructions, tell a short evidence-led demo story, and
prepare for fragile live dependencies.

## Deliverables

- completed [Release and Demo Package](./release-demo-package-template.md);
- completed [README Checklist](./readme-checklist.md);
- completed [Demo Runbook](./demo-runbook-template.md);
- updated project README and linked evidence artifacts;
- final rubric evidence map and self-check.

## 1. Freeze the package candidate

Record the commit/tag, environment, model/config versions, and artifact locations you intend
to demonstrate. Run the primary workflow and preserve its current evidence before rewriting
documentation or rehearsing.

Documentation cannot convert an unverified feature into a release claim. Mark incomplete or
unavailable paths honestly.

## 2. Make the README stranger-runnable

Write for a technically capable person with no access to your memory, shell history, or
private setup. Include:

1. purpose, intended user, and primary workflow;
2. prerequisites and exact setup commands;
3. configuration variables, safe defaults, and secret sources;
4. exact run, test/eval, and deploy/verify commands;
5. architecture as built and important boundaries;
6. evaluation method, versioned results, and links;
7. safety controls, residual risks, and escalation behavior;
8. known limitations and unsupported use.

For every command, state the working directory, prerequisites, and expected success signal.
Never include secret values.

## 3. Verify the documented path

Use a clean clone, fresh environment, container, or equivalent reset. Follow only the README.
Record:

- environment and commit;
- steps attempted;
- first failure or ambiguity;
- correction made;
- final outcome and evidence.

If another person cannot test the path, state the constraint and use the strongest available
independent verification. Do not label an untested instruction “verified.”

## 4. Build an evidence-led demo story

Keep the story concise:

> **User problem → representative input → system decision/action → outcome → evidence →
> limitation**

Choose claims that matter. Pair each claim with a visible artifact such as a trace span, eval
row, safety check, deployment health signal, or versioned output. Avoid a feature inventory.

## 5. Prepare the fallback ladder

For each fragile dependency—network, hosted model, external API, deployment, data source,
authentication, or slow evaluator—prepare:

1. **live path:** exact action and success signal;
2. **safe retry:** bounded retry or deterministic reset;
3. **captured evidence:** current screenshot, trace, log, or recording with version/date;
4. **local/static explanation:** smallest artifact that still proves the claim.

State the transition sentence you will use. A fallback should preserve the same claim and
release version. It must not simulate success or hide a failure.

## 6. Map the rubric to evidence

For every final rubric criterion, record:

- criterion and your claim;
- exact artifact path, URL, command, trace, or timestamp;
- what the reviewer should observe;
- status: proven, partial, missing, or not applicable with rationale;
- gap owner and next action.

Narration alone is not evidence.

## Pace bars

- **Minimum:** all README sections present, one timed primary-path story, one fallback for
  each fragile dependency, and a complete rubric map with honest gaps.
- **Target:** a stranger verifies the primary path from the README; all demo claims link to
  current evidence; the fallback ladder is rehearsed; checklist is complete.
- **Stretch:** versioned release/integrity links, verified alternate or recovery path,
  peer-timed live and fallback rehearsals, and no narration-only rubric criteria.

## 7. Rehearse and self-check

Run the demo from the package, not from memory. Time each beat. Practice one forced fallback.
Then use the checklist and rubric map to remove unsupported claims, stale links, hidden
setup, and timing risk.

## Troubleshooting

**“It works on my machine.”**
- Reset the environment and follow only the README. Every remembered step is missing
  documentation.

**“The reviewer cannot access my hosted service.”**
- Document deployment verification and provide versioned captured evidence plus a local or
  static fallback. State the access boundary.

**“My demo is too long.”**
- Keep one representative workflow and only the evidence needed to prove its important
  claims. Move secondary features to backup material.

**“The live model/API is unreliable.”**
- Use a bounded retry, then switch promptly to labeled captured evidence from the same
  release. Do not improvise repeated retries.

**“A rubric item is not complete.”**
- Mark it partial or missing, link what exists, and name the next action. Do not inflate the
  self-score.

**“The architecture diagram shows the plan, not the implementation.”**
- Update it to the system as built and mark external, trust, data, and human boundaries.
