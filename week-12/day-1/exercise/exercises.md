# Week 12 · Day 1 — Exercise: Write Your Capstone Project Brief

Today you turn an idea into a **project brief** you can defend. No code — the goal is to decide *what* you
are building, *for whom*, and *how you will know it worked*, before you build it. This brief is the
foundation for the whole capstone: Tuesday's evaluation plan, Wednesday's architecture, and Thursday's
repo all start from it.

**Deliverable:** a completed [`project-brief-template.md`](./project-brief-template.md), filled in for
your own idea, with all six sections done.

**Time:** ~25 minutes — about 18 minutes drafting solo, then ~7 minutes swapping with a partner and
checking each other's briefs against [`capstone-rubric.md`](./capstone-rubric.md).

---

## Instructions

Work through the template top to bottom. Keep every section tight — a brief you can say out loud beats a
long document.

1. **Pick your archetype.** Which of the five is your idea? Justify it in one line, and name the
   runner-up if two fit.
   - support assistant · workflow automation · research/analysis · tool/integration · multi-agent
   - **Default to the simplest archetype that fits.** For a solo, three-week build that is almost always a
     *single* agent. Multi-agent is a stretch goal, not a v1.

2. **Write the one-line problem frame.** Fill every slot:
   > "For **\<user\>**, who **\<need\>**, the agent **\<capability\>**, so that **\<outcome\>**."
   - **user** = one specific person in one situation (not "everyone").
   - **need** = a real problem (not a feature).
   - **capability** = the single most valuable thing it does (not five things).
   - **outcome** = the value created — this is where your success metric comes from.
   - If you cannot fill a slot, the idea is not scoped yet. Keep pushing until all four are true.

3. **Describe users & context.** Who uses it, and in what setting (their goal, their environment, what
   they have in front of them when they reach for your agent).

4. **Scope it to a three-week v1.** Write **two** lists:
   - **In scope:** the core job, one happy path through it, one real tool. The smallest thing that would
     actually prove the idea works end-to-end.
   - **Out of scope:** at least **three** things you are explicitly *not* building in v1 (extra features,
     edge cases, polish, scale). This list is not optional — it is what makes the plan real.

5. **Define 2–3 success metrics**, each with a **target number**:
   - at least one **outcome** metric (did it do the job the user came for?), and
   - at least one **quality** metric (was the output correct and grounded?),
   - optionally one **guardrail** (cost, latency, or safety stays in bounds).
   - "It works" is a wish. "Resolves 8 of 10 test cases" is a metric. Every metric needs a number you
     could check with a script, a stopwatch, or a judge.

6. **Name your top risks & unknowns.** The few things that could sink the project, and what you must learn
   early to de-risk it. An idea with no named risk usually has an unspotted one.

---

## Expected outcome (minimum requirements)

Your brief is done when **all** of these are true — this is exactly what your partner (and your coach)
will check against the rubric:

- [ ] An **archetype** is chosen, with a one-line justification.
- [ ] A **one-line frame** with all four slots filled (user, need, capability, outcome).
- [ ] The **user** is one specific person, and the **capability** is one job.
- [ ] **Scope** has both an in-scope and an out-of-scope list; out-of-scope has **at least three** items.
- [ ] **2–3 success metrics**, including at least one outcome and one quality metric.
- [ ] **Every metric has a target number** you can check.
- [ ] **Top risks** are named honestly.
- [ ] You can **read your frame and headline metric out loud** and have it make sense to a partner.

---

## Pair review (last ~7 minutes)

Swap briefs with a partner. For each other's brief, do two things:

1. Read the one-line frame back to its author and ask: *is the user specific? is the capability one
   thing?*
2. Point at each metric and ask: *what is the number, and how would you check it?*

Mark the two or three weakest rows against the rubric. You are not fixing the idea — you are finding the
gaps its author cannot see.

---

## If you finish early

Pick one — both are bridges to later in the week, not extra scope:

- **Draft one golden-set row** (a bridge to Tuesday): write one concrete example input your agent will
  get, and the behaviour you would expect back. This is the first row of the evaluation plan you build
  tomorrow.
- **Sketch the one-sentence architecture** (a bridge to Wednesday): in one sentence, name the pieces your
  archetype implies — the model, the one tool, where knowledge/state lives — without designing them yet.

> Do **not** start writing code or setting up a repo today. Foundation is Thursday, and it will be shaped
> by Wednesday's architecture — which is shaped by the brief you are writing right now.
