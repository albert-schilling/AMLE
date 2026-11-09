# Week 12 · Day 5 — Exercise: Build Your First Vertical Slice

Today is the payoff of the week. You have a brief, an eval plan, an architecture, and a running skeleton.
Now you connect them into **one thin path that works**: one real user input → agent loop → **one** tool
call → a grounded output → a trace → **one of Tuesday's golden rows going green.**

You build it on top of **your own** Thursday skeleton — there is no reference implementation to clone,
because your slice is yours.

**The rule for the whole day: depth, not breadth.** One path all the way through beats five half-built
layers. Only an end-to-end slice reveals whether the pieces actually connect, and only a real eval going
green proves it works rather than merely looks right.

**Deliverable:** a running slice + one green eval, meeting the
[acceptance checklist](./initial-implementation-checklist.md).

**Time:** ~25 minutes in class (many people won't get the row green in the block — that's expected).
**In-class bar:** one real input runs end-to-end to an output. Grounding + the green row can finish by end
of day.

**You need:** your [running skeleton](../day-4/exercise/foundation-setup-checklist.md) (clean clone runs,
no-op traces, one tool wired), your [eval plan + golden set](../day-2/exercise/eval-plan-template.md), and
the golden row you picked in the flipped work.

---

## Instructions

Build in this order — **get the path running before you make it trustworthy, and make it trustworthy
before you claim it passes.** Commit the moment the path runs, then again when the row goes green.

1. **Wire the path: input → loop → one tool → output.** A real user input drives your agent loop (Week 7),
   which makes **exactly one** tool call (the tool from Thursday) and returns an output. One tool, not
   many.
   - **Done when:** one real input produces an output, and the run shows up in your trace.

2. **Build against the trace.** Run the input and watch the spans. When it stalls, the failing span tells
   you where — usually the loop↔tool hand-off or the shape of what the tool returns.

3. **Ground the output.** Make the answer point at the real source it used — a cited document/line, a row,
   or the tool result — so a human (and a judge) can check it (Week 9). Not "based on the docs"; a concrete
   citation.

4. **Make one golden row green.** Take your chosen row from Tuesday's set, run it through the slice, and
   check it against the eval you wrote — a deterministic assertion, or a judge score meeting your
   threshold (Week 11).

Unsure what each hop means for your archetype? See the **"your stack may vary"** table in the
[checklist](./initial-implementation-checklist.md).

---

## Expected outcome (minimum requirements)

Judged against the [acceptance checklist](./initial-implementation-checklist.md). By end of day, **all**
should hold:

- [ ] One real input runs end-to-end (no faked gaps).
- [ ] Exactly one tool call in the path.
- [ ] The output is grounded (cites its real source).
- [ ] The run emits a trace.
- [ ] One golden row's eval passes (green).
- [ ] Everything else is stubbed / deferred.

**In-class minimum:** the first box (one real input runs end-to-end to an output).

**End of week:** you now hold all five Week 12 deliverables — brief, eval plan, architecture, skeleton,
slice — the exact hand-off Week 13 expects.

---

## Troubleshooting (the common blockers)

Work top to bottom — these are the failures that eat the most time.

**"I'm building three things and none of them run."**
- You've gone horizontal. Stop and pick the thinnest path to a green row: one input, one tool doing one
  case, a rough prompt. Get *that* running end-to-end first. Breadth is next week.

**"My path stalls somewhere in the loop."**
- Debug from the trace, not by reading code. Find the last span that succeeded; the break is right after
  it. It's most often the loop→tool hand-off or the tool returning a shape your loop didn't expect.

**"The tool returns something, but my agent does the wrong thing with it."**
- Check the *shape* of the tool result against what the loop expects. Normalize it at the boundary. This
  seam is exactly what a vertical slice exists to find early.

**"My output isn't grounded / the judge dings it."**
- Make the answer cite the actual source it used — the specific line/row/result, with a marker — and
  answer *from* that, not from the model's memory. If your archetype is retrieval-light, "grounded" means
  faithfully reflecting and naming the real tool result.

**"The golden row won't go green."**
- That's information. In order: is the path running to an output? is the output grounded? does the eval
  assert the right thing? is the threshold realistic? Fix in that order. **Do not loosen the eval to force
  a pass** — if the bar really was wrong, change it deliberately and write down why.

**"My skeleton isn't actually running or tracing."**
- That's today's first job — you can't slice on a base that doesn't run. Go back to Thursday's
  [troubleshooting list](../day-4/exercise/exercises.md) and get the skeleton green first.

---

## If you finish early

Both are bridges to Week 13, not extra scope:

- **Add a second golden row** to the *same* slice and make it green too — more proof, same path.
- **Tighten the grounding** — cite the exact line, not just the document, so the judge dimension scores
  higher.

> Do **not** start a second feature today. Protect the thin slice — a path that works and proves itself is
> the foundation next week widens into features.
