# W7D3 Exercise — Framework Evaluation Memo

## Scenario

Over the last two days, Priya took ScoutBot from a script that free-text-parsed a model's
reply, to a hand-rolled agent loop with tools, a stopping condition, and a human-approval gate.
It works — but Priya now owns every line of that loop plumbing herself.

Her manager, **Dana**, has two things brewing for later:

1. She wants ticket escalation to be **more reliable** than a single confirm-prompt gate.
2. She's starting to wonder whether ScoutBot should eventually become **several specialist
   bots** (e.g. one for billing, one for technical issues) instead of one bot with many tools.

Before building anything, Dana wants a short, honest recommendation: given today's four
framework categories, what should Anchorpoint actually consider — and why?

## Starting point

There's no starter code for this exercise — today's deliverable is a **written memo**, not a
build. You'll need:

- Today's live lesson slides (the four framework cards + the landscape and decision-framework
  tables) — you're encouraged to reference them directly.
- `memo-template.md` in this folder — the scaffold your memo should follow.

## Your task

Individually or in pairs:

1. **Pick 2 of the 4 framework categories** from today's session (Anthropic `tool_runner`,
   OpenAI Agents SDK, LangGraph, or CrewAI). Pick two that sit in **different quadrants** of the
   landscape grid (e.g. one lightweight helper + one full workflow engine, or one single-agent +
   one multi-agent) — two frameworks from the same quadrant won't give you much to contrast.
2. **Compare them** on at least these three axes: what each adds beyond a hand-rolled loop, how
   much new complexity/vocabulary each introduces, and which of Dana's two brewing needs (more
   reliable escalation, or eventual multi-bot specialization) each is better suited to.
3. **Make a recommendation.** Pick one of Dana's two needs (state which one), recommend one of
   your two frameworks for it, and justify the choice using your comparison — not just "it
   sounds more popular."
4. **Name what you'd want to prototype first** before Anchorpoint actually commits — one or two
   concrete unknowns you couldn't answer from documentation alone (e.g. "how it behaves when a
   tool call fails," "actual latency of a multi-step run").
5. Fill in `memo-template.md` with your answers and save it as `memo.md` in this same folder.

## Expected outcome (minimum requirements)

- [ ] Two frameworks compared, chosen from different quadrants of the landscape grid
- [ ] Comparison covers: what each adds beyond a hand-rolled loop, complexity/vocabulary cost,
      and fit against Dana's two brewing needs
- [ ] A single clear recommendation, tied to one specific named need, with a stated reason (not
      just a preference)
- [ ] At least one concrete thing you'd want to prototype before committing
- [ ] Saved as `memo.md`, following `memo-template.md`'s structure

## If you finish early

- Sketch (in words, not code) what Anchorpoint's ScoutBot would look like under your
  recommended framework — what would the "tools" or "roles" be called, and who owns what?
- Write a one-paragraph counter-argument for the framework you *didn't* pick — the strongest
  honest case for the other side.

## If you're running out of time

It's fine to submit a rough draft today (2 frameworks named, one clear recommendation) and
finish the full comparison and "what to prototype first" sections before tomorrow's session —
flag what's incomplete rather than leaving it unstated. (Coaches: see the coaches' page
"Contingency plans" for exactly what to prioritise.)
