# W7D1 Exercise — Rebuild ScoutBot's Core

## Scenario

Priya just joined Anchorpoint's support-ops team and inherited **ScoutBot**: a script,
built by a departed colleague (Jonas), that triages support tickets by asking an LLM to
describe the ticket and then regex-parsing the reply. It "works" on one laptop, with one
hardcoded API key. Her manager, Dana, wants it live for the whole team by Friday.

Today, you're Priya's team.

## Starting point

`scoutbot-starter/` contains Jonas's actual handover:

- `scoutbot_final_v3.py` — the script (hardcoded key, regex-parsed replies, no tests)
- `sample_tickets.json` — the 3 tickets ScoutBot needs to triage
- `requirements.txt` — unpinned

## Your task

Working in pairs, on a new branch:

1. **Set up**
    - Copy `scoutbot-starter/` into your own working repo (or branch, if you're using a shared
      template repo).
    - Create a `.env` file (never commit it) with your own `ANTHROPIC_API_KEY`.
    - Move the hardcoded key out of the script and into `.env`.
2. **Restructure**
    - Create `src/scoutbot/` and move the triage logic out of the script into a real,
      callable function — not top-level code that only works if you run the whole script
      start to finish, in order, every time.
    - Add a `.env.example`, a `.gitignore` (ignoring `.env`, `__pycache__/`), and pin your
      dependencies.
3. **Replace the parsing**
    - Define a schema for a triage result: `category`, `priority`, `suggested_owner`.
      Use an enum for `priority` (and ideally `category`) — not a free string.
    - Implement **one tool call** so the model returns arguments matching that schema,
      instead of free text you regex-parse.
4. **Prove it works**
    - Write `main.py` so it runs all 3 tickets in `sample_tickets.json` and prints each
      validated result.
    - Write at least one test that checks your schema rejects an invalid value (e.g. a
      priority that isn't `low`/`medium`/`high`).
5. **Open a PR**
    - Commit your work on the branch and open a pull request back to `main` — even solo,
      practice the habit.

## Expected outcome (minimum requirements)

- [ ] `src/scoutbot/` exists with the triage logic as a callable function (not top-level
      script code)
- [ ] No real secret committed anywhere — `.env` is git-ignored, `.env.example` documents the
      required variable(s)
- [ ] One tool call returns a schema-validated result — not a regex-parsed free-text reply
- [ ] `priority` is a constrained enum, not a free string
- [ ] `main.py` runs against all 3 sample tickets and prints a validated result for each
- [ ] At least one passing test
- [ ] Work is on a branch with an open pull request

## If you finish early

- Add a second tool, e.g. `escalate_to_human()`, and have the model choose between triage and
  escalation.
- Handle the case where the model's output fails schema validation — retry once, then raise or
  log clearly rather than silently guessing.

## If you're running out of time

It's fine to stop once you have the tool call + schema working, even without the full repo
restructure or the branch/PR step — flag what's missing rather than hiding it. (Coaches: see
the coaches' page "Contingency plans" for exactly what to prioritise when a pair is behind.)
