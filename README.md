# Agentic MLE

Student and teacher-facing material for the **Agentic Machine Learning Engineering**
bootcamp track: each day's hands-on exercise, its starting code, and (where the exercise is
a build, not a written task) the tests it needs to pass.

Lesson slides (Flipped Content and Live Lesson decks) are **not** in this repo — they're
maintained and polished as Google Slides and shared with each cohort separately. Instructor
material (coaches' pages, worked reference solutions) is also maintained separately and
isn't published here.

## How this repo is organized

```
week-{WW}/
  day-{D}/
    exercise/
      exercises.md          <- the day's task: scenario, steps, and what "done" looks like
      <starter-code>/        <- your starting point for the day (if the exercise involves code)
```

- **`exercises.md`** is always the actual assignment — scenario, the steps to work through,
  the minimum requirements for "done," an "if you finish early" stretch goal, and what to do
  if you're running out of time. Start here for every day.
- The starter-code folder name varies a little day to day (e.g. `scoutbot-starter/`,
  `scoutbot-baseline/`) — `exercises.md` always says which one to use and what's already
  inside it. Not every day has one: a written-exercise day (e.g. Week 7 Day 3) only has
  `exercises.md` plus a template to fill in.

## Current coverage

- **Week 7** — Foundations of Agentic AI: From LLM Call to Agent Loop (Days 1–5)
- **Week 8** — Stateful Workflows & Observability (Days 1–5)
- **Week 9** — Agentic Knowledge: RAG & Memory (Days 1–5)
- **Week 10** — Tool Integration & the Modern Agent Stack (Days 1–5)
- **Week 11** — Multi-Agent Orchestration & Production Discipline (Days 1–5)
- **Week 12** — Capstone: Discovery & Foundation (Days 1–5)
- **Week 13** — Capstone: Implementation & Midterm (Days 1–5)
- **Week 14** — Capstone: Production & Graduation (Days 1–5)

More weeks are added as they're finished — this is a living repo, not a finished product.

## Setup (code exercises)

You need [`uv`](https://docs.astral.sh/uv/getting-started/installation/) installed. It
creates the Python environment for each exercise and installs the exact dependency versions
recorded in that folder's `uv.lock`.

Each starter folder's own `README.md` has the exact commands for that day — they vary a
little (Week 7 Day 1's starter, for instance, is deliberately just one flat script with no
`.env` or tests yet, since setting those up properly is part of the exercise). From Day 2
onward, the usual pattern is:

```bash
cd <starter-folder>
cp .env.example .env   # then fill in your own ANTHROPIC_API_KEY
uv sync                # creates .venv/ and installs the locked dependencies, pytest included
uv run pytest          # confirm the starting point's own tests pass before you change anything
```

Run scripts the same way (`uv run python main.py`), so nothing depends on activating the
environment first. On days that introduce a new dependency, `exercises.md` tells you to
`uv add "<package>>=x,<y"`, which pins it in `pyproject.toml`, updates `uv.lock`, and installs
it in one step.

Every exercise needs your own `ANTHROPIC_API_KEY` — none of the sample data is real, but the
model calls are.
