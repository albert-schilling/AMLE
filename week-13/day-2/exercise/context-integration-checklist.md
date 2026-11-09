# Context Integration — Acceptance Checklist

> Choose the smallest strategy that makes the primary workflow correct. More persistence
> is not automatically better, and **none** is valid when justified.

## Minimum — protect the decision and boundary

- [ ] I completed the [Context Decision Record](./context-decision-record.md).
- [ ] The required behavior and information are explicit.
- [ ] I chose retrieval, state, short-term context, durable memory, or none with rationale.
- [ ] The boundary identifies source, scope/owner, read/write rules, and expiry.
- [ ] No accidental persistence or cross-scope access exists.
- [ ] The primary workflow and existing regression evidence remain green.

## Target — implement and prove

- [ ] The chosen strategy is implemented behind one context boundary.
- [ ] One representative positive case changes behavior correctly.
- [ ] One isolation/negative case proves unrelated context remains absent.
- [ ] Context reads/writes appear safely in the trace.
- [ ] One grounding, state, context, memory, or isolation eval passes.
- [ ] Offline tests use separate fixtures/scopes and do not require the network.

## Stretch — deepen the same decision

Complete the target, then choose one:

- [ ] Add an irrelevant-source or retrieval-quality negative case.
- [ ] Test expiry/deletion behavior.
- [ ] Add a second scope-isolation case.
- [ ] Measure retrieval/context cost or latency.

Stretch does not mean adding another memory system.

## Definition of done

> The context has earned its place: it changes a required behavior, enters through an
> explicit boundary, remains isolated, appears in the trace, and passes a relevant eval.
