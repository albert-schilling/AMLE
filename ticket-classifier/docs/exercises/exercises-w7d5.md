# W7D5 Exercise — Log It, Then Prove It

## Scenario

ScoutBot's Thought/Action/Observation trace has only ever gone to a terminal and vanished
the moment it scrolled past. The flipped material asked: if ScoutBot ran overnight on 200
tickets and one went wrong, what would you already want to have, to figure out what
happened without re-running anything? Today you build exactly that: a saved record of
every step, then a real answer pulled from it.

## Starting point

`scoutbot-baseline/` is Day 4's reference solution — the bounded ReAct loop with two client
tools and two server tools (`web_fetch`, `code_execution`), unchanged. **Everyone extends
this same baseline today, in place** — there's no new starting point to learn, only one new
piece bolted onto a loop the room already understands. Also inside:

- `sample_tickets.json` — the same 5 tickets as Day 4 (3 from Day 2, plus `T-2001` and
  `T-2002` for the two server tools).
- `sample_app.log` — the same small sample log `T-2002` parses via `code_execution`.

## Your task

Working in pairs, on a new branch, extending `scoutbot-baseline/` in place:

1. **Add a small logger**: one JSON line per loop step, appended to a file, with at least
   `ticket_id`, `step` (number), `tool`, `duration` (however you measure it), and whether it
   errored. No new dependency needed — `json` and `open()` are enough.
2. **Wire it into the loop** so every step gets logged, client tool or server tool alike —
   the log call shouldn't need to branch on which kind of tool a step used.
3. **Run the full sample ticket batch end to end**, then **answer one real question
   straight from the saved log file**, without re-running anything (e.g. how many steps
   errored, which tool ran most, or which step was slowest).
4. **Same habit as every day**: commit on your branch, open a PR back to main.

## Expected outcome (minimum requirements)

- [ ] **Logger**: one JSON line per step, with real fields (not placeholders) — at least
  `ticket_id`, `step`, `tool`, `duration`, `errored`
- [ ] **Loop hook**: every step gets logged, client tool or server tool alike
- [ ] **Full batch run**: every sample ticket processed end to end, with logging on
- [ ] **One real answer**: pulled from the saved file after the batch finishes, without
  re-running any ticket to get it
- [ ] At least one test covering the logger itself and/or the loop's new logging behavior
  (mocking the model, same pattern as every earlier day)
- [ ] Work is on a branch with an open pull request

## If you finish early

- Have your "one real answer" become three: how many steps errored, which tool ran most,
  and which single step was slowest — printed together as a short summary once the batch
  finishes.
- A step that used a server tool doesn't get its own individually-timed duration the way a
  client tool step naturally could (Anthropic's response doesn't expose that). Think through
  out loud (to your pair or a coach) what you'd need to change to get real per-server-tool
  timing, without actually building it.

## If you're running out of time

It's fine to stop once the logger is wired in and produces one real, correctly-shaped line
per step, even if you haven't gotten to pulling an answer back out of the file yet — flag
that the query step is missing rather than skipping past it silently. The full-batch run
matters more than a polished summary format.
(Coaches: see the coaches' page "Contingency plans" for exactly what to prioritise.)

## Answer from the saved log

Question: which step was slowest? Asked of `output/trace.jsonl` after the full batch
(8 tickets, 13 steps), without re-running anything.

```
python3 -c "import json;s=[r for r in map(json.loads,open('output/trace.jsonl')) if r['type']=='step'];m=max(s,key=lambda r:r['duration_ms']);print(m['ticket_id'],m['step'],m['duration_ms'])"
```

Result: `T-2001 3 27126`, so ticket T-2001, step 3, 27.1 s. The step time includes the wait
for human approval, so this may be the approval prompt.

### The same with grep and awk

Each line is one JSON object, so `grep` works on it. These rely on the `": "` spacing
that `json.dumps` writes.

Errored steps (`-c` counts matching lines):

```
grep -c '"errored": true' output/trace.jsonl
```

Escalated tickets (only `final` lines hold the outcome):

```
grep '"type": "final"' output/trace.jsonl | grep '"escalated": true'
```

Three slowest steps (`-o` prints only the match, `sort -n` sorts by number):

```
grep -o '"duration_ms": [0-9]*' output/trace.jsonl | sort -t: -k2 -n | tail -3
```

Ticket with the most total time (`awk` sums the step times per ticket):

```
grep -oE '"ticket_id": "[^"]*"|"duration_ms": [0-9]*' output/trace.jsonl \
  | awk -F': ' '/ticket_id/{id=$2} /duration_ms/{t[id]+=$2} END{for(i in t)print t[i], i}' \
  | sort -n | tail -1
```

Result: `39314 "T-2001"`, so T-2001 used 39.3 s in total (approval wait included).
