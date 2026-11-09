# Week 13 · Day 2 — Exercise: Integrate Only The Context You Need

Today you decide whether the primary workflow needs source knowledge, workflow state,
short-term context, durable memory, or explicitly **none**. Then you implement the smallest
correct boundary and prove both usefulness and isolation.

**Deliverables:**

- [Context Decision Record](./context-decision-record.md)
- [Context Integration Checklist](./context-integration-checklist.md)
- Code, trace, offline tests, and eval evidence in your own repository

## 1. Start from behavior

Choose one representative input or golden row and ask:

> What correct answer or action cannot happen from this input alone?

If nothing is missing, choose **none** and document why. Do not add persistence merely
because an agent can have memory.

If information is missing, classify it:

- facts outside this run → **retrieval / source knowledge**;
- current process position → **workflow state**;
- earlier turns in this session → **short-term context**;
- information required in future sessions → **durable memory**.

Complete Sections 1–2 of the decision record before choosing technology.

## 2. Define the boundary

Specify:

- source/store;
- user/run/session/task ownership key;
- allowed reads and writes;
- expiry or deletion rule;
- sensitive data that must not be stored or traced;
- safe trace metadata.

Keep workflow code behind one adapter or contract. The workflow should not reach directly
into a database, vector store, checkpoint store, or memory service.

## 3. Implement at your pace

- **Minimum:** complete the decision, create a testable boundary, and prove no accidental
  persistence. Preserve Monday's workflow.
- **Target:** implement the strategy and pass one positive context/grounding eval plus one
  isolation case.
- **Stretch:** add expiry, irrelevant-source, quality, or additional isolation evidence.

If you chose **none**, implement proof appropriate to that choice: no store access occurs,
the workflow remains correct, and repeated/unrelated runs do not acquire hidden context.

## 4. Prove both sides

### Positive

Provide the relevant context and assert that behavior changes correctly.

Examples:

- a retrieved source is cited;
- the workflow resumes from its own checkpoint;
- a prior turn changes the answer within the same session;
- a permitted durable preference appears in a later session.

### Isolation / negative

Change the scope and assert the context is absent.

Examples:

- another user cannot retrieve the first user's memory;
- another run does not inherit workflow state;
- an irrelevant document is not cited;
- expired context no longer changes the answer.

Run both offline with explicit fixtures and scope identifiers.

## Troubleshooting

**“I know which database I want, but not the behavior.”**
- Stop implementation. Return to one golden row and name the missing information.

**“Everything sounds like memory.”**
- Ask when the information is needed. Outside facts are knowledge; current process position
  is state; current-session history is short-term context; future-session recall is memory.

**“The positive test passes, but I cannot test isolation.”**
- Your ownership/scope key is probably implicit. Make it part of the context contract and
  create separate fixtures for A and B.

**“Raw user content appears in traces.”**
- Redact it. Trace operation, scope identifier, result count, latency, and safe metadata—not
  sensitive payloads.

**“The context is stale.”**
- Define expiry, invalidation, or a source-of-truth refresh. Durable does not mean permanent.

**“Adding context broke Monday's workflow.”**
- Return to the last green commit. Keep the context adapter injectable, rerun existing
  tests/evals, and add one boundary at a time.

## If you finish early

Choose one:

- add an irrelevant-context negative case;
- test expiry or deletion;
- measure context/retrieval latency;
- tighten citation precision.

Deepen evidence for the chosen strategy; do not add another context system.
