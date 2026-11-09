# Week 12 · Day 2 — Exercise: Write Your Capstone Evaluation Plan

Today you turn yesterday's success metrics — which are still **guesses** — into an **evaluation plan** you
could actually run against your v1. No code: the goal is to decide *what "good" means* and *how you will
measure it*, before you build. This plan is the bridge from your brief to Week 13, where you will run it
against your real agent and iterate.

**Deliverable:** a completed [`eval-plan-template.md`](./eval-plan-template.md), filled in for your own
agent, with all six sections done — and **at least three golden rows**.

**Time:** ~25 minutes — about 18 minutes drafting solo, then ~7 minutes swapping with a partner and trying
to **break** each other's plans.

**You need:** yesterday's [project brief](../day-1/exercise/project-brief-template.md) in hand. Every eval
today traces back to a success metric in it. Judging uses Part A of the
[capstone rubric](../day-1/exercise/capstone-rubric.md) plus the self-check at the bottom of the template.

---

## Instructions

Work through the template top to bottom. Keep every section tight — a plan you could run beats a plan you
could publish.

1. **Copy your metrics from the brief.** List your 2–3 success metrics in section 1. Everything below must
   measure one of these. If a check here matches no metric (or a metric has no check), one of the two
   documents is wrong — fix it now.

2. **Write your golden set (this is the core of today).** At least **three** real rows, each with:
   - **input** — a real thing the user sends,
   - **expected** — what a good agent does with it,
   - **checks** — what this row verifies (a fact, a tone, a format).
   - **At least one row must be awkward:** an edge case, an ambiguous input, or something the agent
     *should refuse*. A golden set of only happy paths passes everything and teaches nothing.
   - **Aim for variety, not volume.** Three sharp rows beat thirty near-duplicates.

3. **Mark your metric ladder.** Which of the five rungs does your v1 actually need — smoke/structural,
   deterministic correctness, grounding, judge quality, outcome/task success? Run the cheap ones often;
   batch the expensive ones. A simple agent may live mostly on rungs 1, 2, and 5.

4. **Write your judge rubric.** For output that is a matter of degree, name the **dimensions** an
   LLM-as-judge will score (correctness and grounding are almost always two), and for each, say what a
   **3 (good, shippable)** looks like. Use the fixed **1–4 scale** — 1 fails, 2 weak, 3 good, 4 excellent,
   **no neutral middle.** The rubric must be concrete enough that two people would score the same answer
   the same.

5. **Set your ship-if threshold.** State the bar as a **number**:
   > "Ship-if ≥ **\_\_\_%** of golden rows score **≥ 3 on every dimension**."
   - *Every* dimension matters — an answer that is correct but ungrounded should not pass.
   - The number will feel arbitrary. That is fine — it is a starting bar you will tune with real data in
     Week 13.

6. **Name your top failure modes.** The few ways your agent could **fool the eval** — pass the bar while
   being wrong, or fail where the golden set does not look. For each, name the check that would catch it.
   The one that bites everyone is **confident-but-wrong**: an answer that looks great and is false.

---

## Expected outcome (minimum requirements)

Your plan is done when **all** of these are true — this is exactly what your partner (and your coach) will
check:

- [ ] Every metric in section 1 **traces to a Day 1 success metric**.
- [ ] **At least 3 golden rows**, each with input, expected, and checks.
- [ ] **At least one golden row is awkward** — an edge case, ambiguous input, or a should-refuse case.
- [ ] The **metric ladder** rungs are marked for what your v1 actually needs.
- [ ] A **judge rubric** naming its dimensions, on the **1–4 scale**, with a concrete "what a 3 looks
      like" for each.
- [ ] A **ship-if threshold stated as a number** ("≥ X% score ≥ 3 on every dimension").
- [ ] **Top failure modes** named, each with the check that would catch it.
- [ ] You can **read one golden row and your ship-if bar out loud** and have them make sense to a partner.

---

## Pair review (last ~7 minutes) — try to break it

Swap plans with a partner. Your job is not to admire the plan — it is to **break** it. For each other's
plan, find:

1. **An input the golden set misses.** A real thing the user might send that no row covers. If you find
   one, that is a new golden row.
2. **An answer that passes the bar but is wrong.** Could the agent hit "≥ 3 on every dimension" while
   still being confident-but-wrong? If so, which check is missing?

Hand back the two gaps you found. This is exactly how real evals get hardened — the plan is "done" only
when a motivated partner cannot easily break it.

---

## If you finish early

Pick one — both are bridges to later, not extra scope:

- **Write the actual judge prompt for one dimension** (a bridge to Week 13): the real text a model would
  receive to score, say, *correctness* on your 1–4 scale. This is what you will run next week.
- **Add one adversarial golden row** that targets your top failure mode: the input most likely to make
  your agent look right while being wrong.

> Do **not** start writing code or setting up a repo today. Foundation is Thursday, shaped by Wednesday's
> architecture. Today's job is to know *how you will measure success* before you build toward it.
