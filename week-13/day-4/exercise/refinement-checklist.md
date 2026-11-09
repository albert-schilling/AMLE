# Architecture Refinement — Acceptance Checklist

## Minimum — make the decision implementable

- [ ] One trace, eval, feedback, risk, or complexity signal is linked.
- [ ] A baseline behavior and measure are recorded.
- [ ] The hypothesis connects one change to one measurable effect.
- [ ] One refinement track is selected and justified.
- [ ] The smallest implementation step and rollback point are explicit.
- [ ] The primary workflow and regression guards are named.

## Target — implement and preserve

- [ ] One bounded responsibility, component, or boundary changed.
- [ ] The refinement appears in the trace.
- [ ] The primary workflow still runs.
- [ ] Existing relevant tests/evals remain green.
- [ ] The architecture diagram reflects the system as built.
- [ ] The decision record includes implementation evidence.

## Stretch — compare honestly

- [ ] The same quality, cost, latency, or complexity measure was rerun.
- [ ] The before/after delta is reported.
- [ ] Regressions and trade-offs are visible.
- [ ] A supported, unsupported, or inconclusive result is stated honestly.

## Multi-agent gate

If another agent was introduced:

- [ ] Evidence shows a separable responsibility.
- [ ] Specialized context/tools, useful parallelism, or routing value is explicit.
- [ ] A tool/function/current-loop step was considered and rejected with rationale.
- [ ] One handoff contract is traced and tested.
- [ ] A measurable benefit is compared with added coordination cost.

> “More agentic” is not a measurable benefit.

## Definition of done

> One observed problem led to one bounded change, the primary workflow remained protected,
> and the architecture record states what the comparison actually showed.
