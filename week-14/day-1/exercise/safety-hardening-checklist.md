# Safety Hardening — Acceptance Checklist

## Starting evidence

- [ ] Week 13 hardening backlog and selected item are linked.
- [ ] Baseline commit and eval-suite path/version/hash are recorded.
- [ ] Model, prompt/config, evaluator, environment, and tool identities are recorded.
- [ ] Existing expectations and thresholds were frozen before hardening.

## Minimum — model and prioritize

- [ ] Workflow scope and deployment assumptions describe the actual capstone.
- [ ] Assets, actors, external effects, and out-of-scope areas are explicit.
- [ ] At least one real data or control trust boundary is mapped.
- [ ] Boundary records identify input control and acting identity/credential.
- [ ] Candidate threats name actor, action, boundary, asset, and impact.
- [ ] One risk is prioritized using evidence, severity, exposure, and reversibility.
- [ ] Expected safe behavior is observable.
- [ ] Defense layers and an adversarial acceptance test are specified.

## Defense quality

- [ ] Input checks enforce relevant type, size, format, provenance, or allowed values.
- [ ] Tool access is authorized independently of model/prompt intent.
- [ ] Credentials and operations use least privilege or deny by default.
- [ ] Tool/model outputs are parsed and checked against a schema or policy where relevant.
- [ ] Invalid or uncertain states fail closed where the impact warrants it.
- [ ] Human approval is used only where its risk reduction justifies friction.
- [ ] Any approval gate is bound to the exact action and handles denial/timeout/staleness.
- [ ] Layers do not all depend on the same fallible signal.

Mark non-applicable items with a reason in the Safety Hardening Record.

## Target — implement and test

- [ ] The selected controls are implemented at enforceable boundaries.
- [ ] Adversarial expected behavior was written before the run.
- [ ] Tests include invalid/denied behavior, not only allowed behavior.
- [ ] Adversarial slice results are saved at row level.
- [ ] The unchanged relevant Week 13 suite was rerun.
- [ ] Existing normal-path regressions remain visible.
- [ ] False positives, cost, latency, and uncertainty are recorded.
- [ ] Claims are bounded to the observed evidence.
- [ ] Residual risk, assumptions, monitoring, and next action are explicit.

## Stretch — deepen the same risk

Complete target, then choose one:

- [ ] Add a deterministic safety regression gate.
- [ ] Prove least privilege with an unauthorized/denied-action test.
- [ ] Test approval denial, timeout, stale approval, or bypass.
- [ ] Repeat variable adversarial runs and report uncertainty.

## Final review

- [ ] No difficult eval rows were removed or expectations weakened.
- [ ] No broad “safe” claim replaces a bounded result.
- [ ] No second risk displaced completion of the selected risk.
- [ ] Code/config evidence and the completed Safety Hardening Record are linked.

> The checkpoint proves one risk was modeled, reduced, and tested. It does not prove the
> capstone is risk-free.
