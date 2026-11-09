# ScoutBot Evaluation Decision Guide

Day 2's guide was about levers on a working team (planning, cost). Today's is about the discipline that
keeps it working: **evaluation.** The skill is choosing the *cheapest metric that answers the question* —
most quality checks are properties of the output a string can settle, and only the open-ended ones need a
model. As before, name the problem precisely and the pattern is a lookup.

## Which metric? Match the check to the question

| When you need to know… | Reach for | Why | Cost |
| --- | --- | --- | --- |
| did it reach the right specialist? | a **deterministic `BaseMetric`** (`RoutedCorrectlyMetric`) | routing is a fact in the transcript; compare it to the label | free, no model |
| did a grounded answer cite a source? | a **deterministic `BaseMetric`** (`CitesSourcesMetric`) | citation is a property of the text; a regex settles it | free, no model |
| does the answer invent facts the passages don't support? | a **faithfulness** metric over `retrieval_context` | grounding is checkable against the sources you retrieved | model (named, not built) |
| is this actually a *good*, helpful reply? | an **LLM-as-judge** (`GEval` + a rubric) | quality is a language judgement; only a model reads for meaning | a metered model call |
| did it call the right tools, in order? | `expected_tools` / a tool-trace metric | tool use is observable; assert on it deterministically | free, no model |

**The order is the lesson:** run the free deterministic checks first, and escalate to the judge only for
the question they cannot answer. Most regressions (a mis-route, a dropped citation) are caught instantly
and for nothing; the judge earns its cost on answer quality alone.

## Deterministic vs LLM-as-judge — the real trade

| | Deterministic metric | LLM-as-judge (`GEval`) |
| --- | --- | --- |
| Answers | "is this property true?" (routed, cited, called a tool) | "is this *good*?" (on-topic, grounded, helpful) |
| Cost | free | a model call per case |
| Flakiness | none — same input, same score | some — judge variance; pick a threshold with slack |
| When it's wrong | your rule is wrong (fixable, visible) | the judge disagrees with a human (calibrate it) |
| Build it as | `BaseMetric` subclass | `GEval(model=<swappable judge>)` |

## Two decisions that look alike but aren't

- **A test vs an eval.** A unit test asserts a *deterministic* fact (`_parse_plan([]) == ["research"]`)
  and is red-or-green. An eval scores a *model's behaviour* over a dataset and trends a pass rate — a
  judged metric may legitimately sit at 0.9, not 1.0. Keep them separate: tests gate correctness, evals
  track quality.
- **The judge model vs the product model.** The model *under evaluation* is tiered per ticket for
  production cost (Day 2). The **judge** is a *batch, offline* cost paid over a fixed eval set, so it can
  afford the strong tier — the opposite calculus. Don't reflexively make the judge cheap.

## Two spike findings that will bite if ignored

- **Set the deepeval phone-home opt-outs before importing it.** Three env vars
  (`DEEPEVAL_TELEMETRY_OPT_OUT`, `ERROR_REPORTING`, `DEEPEVAL_UPDATE_WARNING_OPT_OUT`), set *before* the
  import, are the difference between "fully offline" and a silent network call. Both modules do this at
  the top.
- **`GEval` scores 0–10 and divides by 10.** The judge fills a `{score: float, reason: str}` schema;
  return `score=9` to mean 0.9. A stub that returns `0.9` yields a final `0.09` — every judged score 10×
  wrong, silently.

## The transferable rule

**You can't improve what you can't measure, and you can't rerun a vibe.** Turn "it looked fine" into a
dataset scored by metrics you run on every change. Lead with the cheap deterministic checks — they catch
most regressions for free — and spend a judge only on the open-ended quality a string can't settle. When
you find a new bug, the fix is not just a patch: it is a new case in the eval set, so the same mistake can
never come back unnoticed.
