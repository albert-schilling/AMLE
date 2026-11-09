# First Vertical Slice — Acceptance Checklist

> This is the **definition of done** for your slice. There is no code to clone — you build one thin path
> on top of *your own* Thursday skeleton, in whatever stack it established. The slice is done when every
> box below is true. **One path, not many features** — that is correct.

**Repo:** _link to your capstone repo_
**Author:** _your name_
**Date:** _today_
**The golden row you're making green:** _paste the one input → expected behaviour row from Tuesday's set_

---

## The six acceptance criteria

- [ ] **One real input runs end-to-end.** A genuine user input goes in and an output comes out — no gap in
  the path is faked or hard-coded.
- [ ] **Exactly one tool call in the path.** The agent loop makes one real tool call (the first tool your
  architecture named). The rest is deferred, not built.
- [ ] **The output is grounded.** The answer cites the real source it used (a document/line, a row, a tool
  result) — not "based on the docs".
- [ ] **The run emits a trace.** You can see every step the slice took (input → loop → tool → output),
  using the tracing you wired Thursday.
- [ ] **One golden row's eval passes.** Your chosen row from Tuesday's golden set goes **green** — a real
  assertion (deterministic) or a judge score meeting your threshold.
- [ ] **Everything else is stubbed or deferred.** No second feature, no second tool, no breadth. That's
  next week.

### In-class minimum (rest can finish by end of day)

- [ ] **One real input runs end-to-end to an output.**

If you have that by the end of the block, you're on track. Grounding + the green row can spill into the
afternoon.

---

## The one true finish line

> **A demo that "looks right" is not done. One golden row going green is.**
>
> Green proves the path genuinely works *and* that your eval harness runs — which is exactly what you'll
> lean on next week to iterate without breaking what works.

If the row won't go green, that's information, not failure — the slice is surfacing a real gap. Debug from
the **trace**, in this order: is the path running to an output? is the output grounded? does the eval
assert the right thing at a realistic threshold? **Do not loosen the eval to force a pass.** If the bar
really was unrealistic, change it deliberately and note why.

---

## "Your stack may vary" — what each hop means for your archetype

You choose the stack. This keeps the four hops concrete without prescribing an implementation. Your
architecture and skeleton are the source of truth.

| Archetype | The one input | The one tool call | What "grounded" means here |
| --- | --- | --- | --- |
| **Support assistant** | one real user question | retrieve from your knowledge base | answer cites the retrieved passage |
| **Workflow / automation** | one real task/event | the first system action (read-only ok) | output names the record/state it acted on |
| **Research / analysis** | one real research query | one fetch/lookup | synthesis cites the fetched source |
| **Tool / integration** | one real request | the primary external API (read endpoint) | output faithfully reflects & names the tool result |
| **Multi-agent** *(stretch)* | one real input to one agent | that agent's single tool | as per that agent's tool |

> Whatever your stack: **one input, one tool, one grounded answer, one green row.** Everything else waits.

---

## Definition of done, in one line

> A teammate could **send one real input, watch it run end-to-end through the loop and one tool, get a
> grounded answer, read the trace, and see one golden row's eval go green.**
