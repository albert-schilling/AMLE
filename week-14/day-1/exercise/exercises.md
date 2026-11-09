# Week 14 · Day 1 — Exercise: Harden One Safety Risk

Use your Week 13 hardening backlog and eval suite to reduce one credible risk in your own
capstone. Today is not a generic security audit and does not prove the system “safe.”

**Deliverable:** a completed
[Safety Hardening Record](./safety-hardening-record-template.md), reviewed against the
[Safety Hardening Checklist](./safety-hardening-checklist.md), plus the corresponding
code/config and saved test evidence in your repository.

**Rule:** model the real workflow, change one prioritized risk, and keep existing behavior
under regression test. There is no canonical implementation.

---

## 1. Freeze the starting evidence

Before editing:

1. Link the Week 13 production-hardening backlog.
2. Record the current commit and eval-suite path/version/hash.
3. Save the latest passing or known baseline result.
4. Record model, prompt/config, evaluator, environment, and relevant tool identities.
5. Do not remove difficult rows or weaken expected behavior after seeing results.

The existing suite is today's regression guard. Add adversarial cases in a distinct slice
so safety evidence and general behavior remain visible.

---

## 2. Model the actual trust boundaries

Draw the workflow you actually expect to run:

```text
actor → input boundary → agent/model → context/data boundary
      → tool authorization boundary → external effect → output/user
```

Your system may have fewer or different parts. For each boundary, record:

- what data or control crosses it;
- who controls the incoming value;
- what identity or credential acts;
- what the receiver assumes;
- what validation, authorization, or approval exists now;
- what asset could be exposed, changed, or misused.

Include boundaries such as user-to-agent, retrieved-content-to-model, model-to-tool,
tool-to-external-service, agent-to-human approver, and output-to-user only when they exist
in your system. Do not invent architecture to make the diagram look complete.

---

## 3. Describe and prioritize one credible risk

Write candidate threats in a concrete form:

> **[Actor/source]** can **[action]** across **[boundary]**, affecting **[asset]** and causing
> **[impact]**, because **[current weakness/evidence]**.

Use backlog items, traces, eval failures, architecture assumptions, or realistic abuse
paths as evidence. Compare:

- severity and reversibility of impact;
- likelihood or exposure;
- detectability;
- current control strength;
- feasibility of meaningful reduction today.

Choose one risk. A rare privacy, safety, financial, or irreversible action may outrank a
frequent low-impact failure; do not multiply scores mechanically.

---

## 4. Design layered, proportionate defenses

Choose only layers relevant to the selected risk:

1. **Input validation:** type, size, format, provenance, allowed values, and normalization.
2. **Tool authorization / least privilege:** allowlisted operations, scoped credentials,
   resource ownership, deny-by-default policy, quotas, or sandboxing.
3. **Output / schema controls:** typed parsing, constrained values, citations, policy checks,
   escaping, and fail-closed handling.
4. **Human approval:** an enforced gate for high-impact, ambiguous, costly, or irreversible
   actions, with enough context for a real decision.

For every layer, state whether it prevents, detects, or contains the threat. Avoid duplicate
controls that fail for the same reason. Prompt instructions may support a layer, but they
do not replace authorization or enforcement.

Write the hypothesis before implementation:

> Because **[risk evidence]**, enforcing **[layers]** at **[boundaries]** should cause
> **[adversarial cases]** to **[safe behavior]** while **[regression guards]** remain green.

---

## 5. Add adversarial and regression tests

Create the smallest representative attack set for the chosen risk. Include, where relevant:

- malformed, oversized, conflicting, or untrusted input;
- instruction injection through user or retrieved content;
- unauthorized tool, resource, tenant, or action;
- malformed or policy-violating tool/model output;
- approval denial, timeout, stale approval, or bypass attempt;
- repeated/replayed action or boundary-condition abuse.

Define the expected safe behavior before running:

- reject with a stable reason;
- ask for missing information;
- constrain or redact output;
- deny the action;
- route to a genuine approval gate;
- or fail closed without the external effect.

Then run all four check types:

1. **positive:** the allowed, valid path still succeeds;
2. **negative:** the disallowed or unauthorized path is refused or fails closed;
3. **adversarial:** the attack slice above takes the safe path;
4. **regression:** the unchanged relevant Week 13 eval suite and deterministic
   unit/contract checks for each new enforcement boundary stay green.

Save row-level results. Record normal-path regressions, latency/cost changes, false
positives, and uncertain or nondeterministic outcomes.

---

## 6. Record residual risk

Complete the Safety Hardening Record. State:

- what the change demonstrably reduced;
- what it did not prove;
- known bypasses or untested assumptions;
- what still depends on a provider, operator, or human;
- detection/monitoring needed after deployment;
- the next safety action and acceptance test.

“Safe” is not a conclusion. Use bounded claims tied to evidence.

---

## Pace bars

- **Minimum:** map actual trust boundaries; prioritize one evidenced risk; specify layers,
  adversarial cases, expected safe behavior, and a testable hypothesis.
- **Target:** implement the layers; run positive, negative, adversarial, and frozen Week 13
  regression checks; complete the record with regressions, trade-offs, and residual risk.
- **Stretch:** add one deterministic safety gate, denied-action least-privilege test,
  approval-bypass/failure test, or repeated adversarial run with uncertainty.

Stretch deepens the same risk. Do not begin hardening a second risk.

---

## Troubleshooting

**“My threat model applies to any chatbot.”**
- Replace generic components with your actual data flow, identities, tools, assets, and
  external effects. Delete boundaries your system does not have.

**“The model refuses the unsafe request.”**
- Test whether the tool or data boundary also enforces the decision. Refusal wording alone
  is not authorization.

**“We need a human in the loop.”**
- Name who approves, what evidence they see, how approval is bound to the exact action, and
  what happens on denial, timeout, or stale approval.

**“The adversarial case is blocked, but normal requests fail.”**
- Record the regression or false positive. Narrow the control without weakening the
  selected safety property, then rerun both slices.

**“I cannot eliminate the risk.”**
- Risk reduction is valid. Document residual severity, assumptions, detection, and the next
  control instead of claiming elimination.

**“I do not have time to run the full suite.”**
- Reduce implementation scope. A defense without adversarial and regression evidence is not
  a completed target checkpoint.
