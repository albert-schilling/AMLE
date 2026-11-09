# Week 12 · Day 3 — Exercise: Draw Your Capstone Architecture

> **Half-day.** Today's slot is shared with the Career Session. This exercise is the architecture half.

Today you turn your brief into a **one-page architecture design**: a topology, a block diagram of the
standard parts, and a trace from every box back to the week that taught it. No code — the goal is to
decide *what the parts are* and *how they wire up*, before you build. This diagram is the blueprint
Thursday's foundation repo is built from.

**The frame for the whole exercise: the capstone is _assembly, not invention_.** Every component you need,
you already built in Weeks 7–11. Today is choosing and wiring, not inventing.

**Deliverable:** a completed [`architecture-template.md`](./architecture-template.md), filled in for your
own agent, with all five sections done — including an actual **drawn block diagram**.

**Time:** ~20 minutes — about 16 minutes drawing solo, then ~7 minutes walking a partner through your
diagram and hunting untraceable boxes.

**You need:** your [project brief](../day-1/exercise/project-brief-template.md) (for the archetype and
scope) and your [eval plan](../day-2/exercise/eval-plan-template.md). Judging uses the self-check at the
bottom of the template plus Part A of the [capstone rubric](../day-1/exercise/capstone-rubric.md).

---

## Instructions

Work through the template top to bottom. Keep it to one page — a blueprint someone could build from beats
a document nobody reads.

1. **Pick your topology.** Which of Week 11's four shapes fits — single agent, orchestrator-worker,
   supervisor/router, or swarm? **Default to a single agent.** Every extra agent is a cost (more parts,
   more failure modes, more to trace), so if you choose more than one, write the *single sentence* that
   justifies it: what does the second agent do that one agent with a tool could not? If you cannot write
   that sentence, make it a stretch goal and build the single-agent version first.

2. **Draw the block diagram.** Using the convention from class, draw your agent: user input at the top, the
   agent core (model + loop) in the middle, tools and memory/retrieval to the sides, grounded output at
   the bottom, and a trace band underneath. **Keep only the parts your agent actually has** — an absent
   part is a deliberate choice, not a hole. Draw it on paper, a whiteboard, or any tool, and paste or link
   it into the template.

3. **Name each component for your project.** Fill the component table: which model, which tool(s), what it
   reads or remembers, what state it keeps, and what you trace. Write "none (why)" for any part your v1
   genuinely does not need.

4. **Trace every box to a week.** Label each box on the diagram with where you learned it — loop (W7),
   tools (W7+10), state and tracing (W8), retrieval (W9), multi-agent (W11). This proves the whole thing
   is assembly, not invention.

5. **List your open decisions.** Any box you *couldn't* trace, plus anything you still need to decide
   before Thursday, goes here. An untraceable box is either unnecessary (cut it) or a real decision (name
   it). A design with zero open decisions on Wednesday is usually hiding them.

---

## Expected outcome (minimum requirements)

Your design is done when **all** of these are true — this is exactly what your partner (and your coach)
will check:

- [ ] A **topology** is chosen and justified in one line (and any extra agent has its one sentence).
- [ ] A **one-page block diagram** exists: user → agent core → tools/retrieval → grounded output.
- [ ] **Every component** is named for your project (or marked "none — why").
- [ ] **Each box traces to a week** — nothing invented from nothing.
- [ ] **Open decisions** are listed honestly.
- [ ] Nothing in the diagram is a part your **v1 does not need** (it matches the brief's scope).
- [ ] You can **narrate the flow** from input to output in a few sentences.

---

## Pair review (last ~7 minutes) — walk it, then hunt orphans

Swap with a partner. For each other's design, do two things:

1. **Have the author narrate the diagram** from user input to grounded output. If they cannot do it in a
   few sentences, the diagram is not done yet — find where it breaks down.
2. **Hunt untraceable boxes.** Point at each box and ask: *"which week is that from?"* Any box that has no
   answer is the most useful thing on the page — it is a tool call in disguise, or scope creep, or a real
   open decision.

Hand back the orphan boxes you found. The design is "done" only when someone else could build from it.

---

## If you finish early

Pick one — both are bridges to later in the week, not extra scope:

- **Mark the first slice** (a bridge to Friday): circle the *one* box, and the one path through the
  diagram, that your first end-to-end vertical slice will exercise. This is what you'll build Friday.
- **Write the trace fields** (a bridge to Thursday): for the agent core, list what each step should log
  (input, tool call, tool result, output) — the observability you'll wire up tomorrow.

> Do **not** start writing code or setting up a repo today. Foundation is Thursday, and it is built from
> exactly the diagram you are drawing right now — so the sharper this page, the smoother tomorrow.
