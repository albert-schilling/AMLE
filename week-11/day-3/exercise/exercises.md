# W11D3 Exercise — Prove It Works (Evals and an LLM-as-Judge)

> **Career Session day.** This is the shorter, technical half of Wednesday. The hands-on is ~25 minutes,
> not the usual ~35 — the rest of the day is the Career Session. Build the **deterministic** eval harness;
> the LLM-as-judge is there to wire with the stub and to read, and to run for real only if you have a key.

## Scenario

ScoutBot is a planning team now: a planner routes, a supervisor delegates, the bill is metered. Priya
asks the one question no day has answered: **how do you know it's any good, and how would you know if a
change made it worse?** "I tried a few tickets and they looked fine" is not something you can rerun on
every commit.

So today you make quality **measurable**. You build an **eval** — a fixed set of labelled tickets scored
by metrics — and you learn the order that matters: **lead with cheap deterministic checks** (did it route
right? did a grounded answer cite a source?), and escalate to an **LLM-as-judge** only for the
open-ended part a string comparison can't settle ("is this actually a *good* reply?").

## Starting point

`scoutbot-baseline/` is **the finished Day 2 planning team** — planner, supervisor, workers, metering,
all passing. Everyone extends this same baseline, in place. Three things to know:

- **Lead with deterministic metrics.** A mis-route or a missing citation is a property of the output a
  regex can settle — free, instant, never flaky. Run those first; a judge is for what they can't answer.
- **The judge is a swappable model.** deepeval lets you pass any `DeepEvalBaseLLM` as the judge. You'll
  wrap your own Anthropic client for real runs and a canned `StubJudge` for tests — the same
  `_client`-patching seam as `core.triage` and `planner.plan_ticket`.
- **deepeval runs fully offline — if you set it up right.** Two facts save you an afternoon: it phones
  home on import unless three env vars are set *first*, and `GEval` scores on a **0–10** scale (it divides
  by 10). Both are called out below.

## Your task

Working in pairs, on a new branch.

> **Step 0 — install the one new dependency of the week.** `uv add "deepeval>=4.1,<5"`. It is deliberately
> not in the baseline's `pyproject.toml`; `uv add` pins it there and in `uv.lock` as it installs.

### Part 1 — The eval harness and deterministic metrics (`src/scoutbot/evals.py`)

1. **A labelled dataset.** An `EvalCase` (ticket id, text, customer id, `expected_route`, `must_cite`,
   optional `refund_amount`) and an `EVAL_SET` of ~6 tickets covering all three specialists, with both a
   cite and a no-cite case. Write the cases so the deterministic team gets them *right* — the eval should
   be green on the reference behaviour, so a future regression turns it red.
2. **Package a run as a test case.** `build_test_cases(...)` runs `build_orchestrator` over the dataset
   (no model call — the dispatcher is a keyword rule) and returns one deepeval `LLMTestCase` per case:
   `input` the ticket, `actual_output` the answer, `retrieval_context` the passages, and the routing facts
   + `must_cite` in `metadata`. Inject `get_customer`/`get_order_status`/`kb` so it runs offline.
3. **`RoutedCorrectlyMetric` (a `BaseMetric`).** No model. Read the observed route back out of the
   transcript (`dispatch->refund`) and compare it to `expected_route`. Set `self.score`/`self.success`/
   `self.reason`; implement `measure`, `a_measure`, `is_successful`, and the `__name__` property.
4. **`CitesSourcesMetric` (a `BaseMetric`).** No model. For a `must_cite` case, the answer must contain a
   bracketed source tag (`[refunds]` — the shape `format_passages` emits); for a case that need not cite,
   pass trivially. The metric asserts only what the case asked for.
5. **A transparent runner.** `run_suite(test_cases, metrics)` loops every case over every metric,
   collecting score / success / reason, and rolls up a pass rate and a `failures()` list. This is the
   whole idea of a harness in one loop — an eval is just metrics run over cases.

### Part 2 — The LLM-as-judge (`src/scoutbot/judge.py`)

6. **Opt out of phone-home *before* importing deepeval.** At the top of the module, set
   `DEEPEVAL_TELEMETRY_OPT_OUT`, `ERROR_REPORTING`, and `DEEPEVAL_UPDATE_WARNING_OPT_OUT` (all to `YES`/
   `NO`) **before** any `from deepeval import ...`. Miss this and import reaches the network.
7. **`StubJudge(DeepEvalBaseLLM)`.** The offline judge: `generate(prompt, schema=None)` returns
   `schema(score=<0-10>, reason=...)` when given a schema (remember GEval divides by 10, so `score=9` →
   0.9), or plain text otherwise. Plus `a_generate`, `load_model`, `get_model_name`. No network.
8. **`answer_quality_metric(judge=None, *, threshold=0.7) -> GEval`.** A `GEval` with an explicit
   `evaluation_steps` rubric (passing the steps makes GEval **skip** its own steps-generation model call),
   `evaluation_params=[INPUT, ACTUAL_OUTPUT]`, and `model=judge or AnthropicJudge()`. Escalate to this
   *after* the deterministic checks.
9. **`AnthropicJudge(DeepEvalBaseLLM)`.** The real judge: `generate` forces a single `submit_evaluation`
   tool call (schema = the one GEval hands it), validates it back, and — if a `Meter` is passed — records
   the call under `"judge"`. Same patchable `_client` seam as `core.triage`. (Judging is a *batch/offline*
   cost, so it can default to the strong tier — the opposite of Day 2's per-ticket tiering.)

### Part 3 — Demos and offline tests

10. **See the eval, no key (`run_evals.py`).** Build the cases, run the two deterministic metrics through
    `run_suite` and print the report, then run everything through deepeval's own `evaluate()` with a
    `StubJudge`-backed answer-quality metric. Fully offline.
11. **See the real judge (`run_judge.py`), needs a key.** Score two hand-written replies to one ticket —
    one grounded/honest, one confidently wrong (invents a refund window) — with the real `AnthropicJudge`,
    and print each score, reason, and the metered cost. This is the case a regex can't make.
12. **Test offline (`tests/test_evals.py`, `tests/test_judge.py`).** Deterministic metrics as pure
    functions over hand-made cases; `build_test_cases` end-to-end with stubs; `run_suite` roll-ups;
    `StubJudge` filling the schema; `AnthropicJudge` through the **patched `_client`** (tool call
    validated, meter recorded, and a raise when the model skips the tool); and `answer_quality_metric`
    passing/failing with the stub. Keep the suite green, commit, open a PR.

> **Two gotchas worth naming.** (1) Set the deepeval env opt-outs *before* the import, or a "fully
> offline" run quietly reaches the network. (2) GEval scores 0–10 and divides by 10 — a stub that returns
> `0.9` gives a final `0.09`, not `0.9`; return `9`.

## Expected outcome (minimum requirements)

- [ ] **A labelled `EVAL_SET`** covering all three specialists, with a cite and a no-cite case, green on
  the reference behaviour
- [ ] **`build_test_cases`** runs the team over the dataset offline and returns deepeval `LLMTestCase`s
- [ ] **`RoutedCorrectlyMetric`** and **`CitesSourcesMetric`** — deterministic `BaseMetric`s, no model
- [ ] **`run_suite`** scores every case × metric and rolls up a pass rate + failures
- [ ] **`answer_quality_metric`** is a `GEval` scored by a swappable judge; **`StubJudge`** runs it offline
- [ ] **`AnthropicJudge`** forces a tool call through the patched `_client` seam and meters the call
- [ ] **deepeval env opt-outs are set before import** — the offline demo touches no network
- [ ] **`run_evals.py`** runs with **no key**; **`run_judge.py`** grades good-vs-bad with a real judge
- [ ] **Offline tests** for both modules; **the whole earlier suite still passes** — the day is additive
- [ ] Work is on a branch with an open pull request

## If you finish early

- **Turn a real bug into a permanent case.** Find a ticket the team gets wrong (the keyword dispatcher
  still mis-routes *"how long do refunds take?"* to refund). Add it to `EVAL_SET` with the *correct*
  expectation and watch it go red — that red is the eval doing its job.
- **Add a faithfulness check.** You already put the passages in `retrieval_context`. Add a metric (or use
  deepeval's `FaithfulnessMetric`) that flags an answer making claims the passages don't support.
- **Judge the judge.** Run `run_judge.py` twice on the same answers. Is the score stable? What does a
  swing of ±1 mean for your `threshold`?
- **Gate on the eval.** Sketch how `run_evals.py`'s pass rate could fail a CI check — what threshold, and
  which metrics are allowed to be soft vs hard?

## If you're running out of time

Protect Part 1 (the dataset, the two deterministic metrics, `run_suite`) and step 12's `test_evals.py`.
That core — *a labelled eval set, scored by free deterministic checks, proving routing and citation, all
offline* — is what the day is assessed on. The LLM-as-judge (Part 2) can shrink to just the `StubJudge`
path plus `answer_quality_metric`; the real `AnthropicJudge` and `run_judge.py` (which need a key) are the
first to trim. **Do not** skip the deepeval env opt-outs (a "fully offline" run that isn't) or the
0–10/÷10 detail (every judged score silently 10× wrong). Flag whatever you skipped rather than quietly
leaving it out. (Coaches: see the coaches' page "Contingency plans".)
