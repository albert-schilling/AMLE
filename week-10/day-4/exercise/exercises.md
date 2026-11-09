# W10D4 Exercise — A Type-Safe, Contract-Driven Triage Agent (Pydantic AI)

## Scenario

Since Week 7, ScoutBot has produced one small contract for every ticket: a `TicketTriage` — a category, a
priority, a suggested owner. And since Week 7 it has produced it the hard way. `core.triage` writes the
tool schema by hand from the Pydantic model, forces the tool call, digs the `tool_use` block out of the
reply, `model_validate`s it, and retries once in a `try/except`. It works. But every line is *plumbing*
wrapped around one tiny contract — plumbing you'd have to write again for the next contract, and the next.

Today you let a framework hold that contract. You build a **Pydantic AI** agent whose
`output_type=TicketTriage`, and the framework derives the schema, requires the model to produce it,
validates the reply, and retries on a miss. The result is the *same* validated `TicketTriage` — but the
code now says *what* you want back, not *how* to coax and check it. Then you add one rule the type itself
cannot express (an **output validator**), and you prove the whole thing **offline**, the framework-native
way.

The theme: type-safe, contract-driven output as a first argument, not a hand-rolled loop. The discipline is
the same as every week — the agent binds **no model** at import, the real model arrives at call time, and
the tests drive it with fake models behind a hard backstop, so nothing ever reaches the network.

## Starting point

`scoutbot-baseline/` is **your finished Day 3 agent — hooks and a subagent.** Everyone extends this same
baseline, in place. Three things to know:

- **The contract already exists.** Reuse `schema.TicketTriage` (and its `Category`/`Priority` enums). Your
  new `typed_agent.triage` must return the same type `core.triage` does — read `core.triage` first, because
  today's agent replaces its *machinery*, not its result.
- **Build the agent with no bound model.** `Agent(output_type=TicketTriage, …)` with **no** `model=` keeps
  `import` key-free. Binding a provider string reads `ANTHROPIC_API_KEY` at construction and breaks the
  offline import (and every test). Put the real model behind a lazy factory and pass it at call time.
- **Prove it with fake models.** `TestModel` and `FunctionModel` drive the agent with no key and no network;
  `pydantic_ai.models.ALLOW_MODEL_REQUESTS = False` is the seatbelt that makes a real call raise. This is
  the same "mock the collaborator that needs the network" move as patching the Anthropic client.

## Your task

Working in pairs, on a new branch.

### Part 0 — Add the dependency

1. **`uv add "pydantic-ai>=2.27,<3"`** — one command installs it and pins it in `pyproject.toml` and
   `uv.lock`. This is today's one new dependency; the baseline omits it on purpose.

### Part 1 — The typed agent (`src/scoutbot/typed_agent.py`)

2. **Build the agent with no bound model.** Create `triage_agent = Agent(output_type=TicketTriage,
   system_prompt=…, retries=1)` — **no `model=` argument.** That one omission is what keeps
   `import scoutbot.typed_agent` working with no API key. `retries=1` is the framework's version of Week 7's
   "retry once, then escalate."
3. **Add a lazy real-model factory.** Write `anthropic_model()` that returns an
   `AnthropicModel("claude-…")`. Constructing it reads the key, so it must only be called at *call time* on
   the demo path — never at import, never in tests.
4. **Write `triage(ticket_text, model=None)`.** Call `triage_agent.run_sync(ticket_text, model=model or
   anthropic_model())` and return `result.output`. Tests pass a fake `model`; the demo passes nothing and
   gets the real one.
5. **Add one output validator.** Decorate a function with `@triage_agent.output_validator` that enforces a
   rule the *type* cannot say — e.g. `suggested_owner` must be a single team handle (`billing-team`), not a
   blank or a sentence. Raise `ModelRetry(...)` when the rule is violated, and the framework re-prompts the
   model (bounded by the same `retries` budget). Types check the form; validators check the meaning.
6. **Export the new pieces** from `__init__.py` (mind the name clash: `core.triage` is already exported as
   `triage`, so alias the new one, e.g. `typed_triage`).

### Part 2 — A demo, and offline tests (`run_typed.py`, `tests/test_typed_agent.py`)

7. **See it work (`run_typed.py`).** Run `typed_agent.triage` over a few sample tickets and print the
   validated result. This path makes real calls, so it needs a key — the *offline* proof lives in the
   tests.
8. **Set the backstop first.** At the top of `tests/test_typed_agent.py`, set
   `pydantic_ai.models.ALLOW_MODEL_REQUESTS = False`. `TestModel`/`FunctionModel` are exempt; a real request
   is not.
9. **Test the happy path with `TestModel`.** Pass
   `TestModel(custom_output_args={"category": "billing", "priority": "high", "suggested_owner": "billing-team"})`
   and assert you get exactly that `TicketTriage` back. Add one with a bare `TestModel()` to show it
   auto-generates a schema-valid result.
10. **Test the retry with `FunctionModel`.** Write a function whose *first* reply is schema-invalid (e.g.
    `priority="urgent!!"`) and whose *second* is valid; assert the framework recovers and that it was called
    exactly twice. Add a second `FunctionModel` test where the first reply is schema-valid but trips your
    output validator (a sentence for the owner), and assert the retry fixes it.
11. **Test the loud failure.** Pass a `TestModel` whose `custom_output_args` never validate (an invalid
    priority) and assert `triage` raises `UnexpectedModelBehavior` once the retry is spent.
12. **Test the backstop and the no-bound-model design.** Assert `triage_agent.model is None`, and assert that
    passing a real `AnthropicModel` (with a dummy key set) raises `RuntimeError` — the guard fires before any
    network call.
13. **Same habit as every day**: bump the version in `pyproject.toml`, keep the whole earlier suite green,
    commit on your branch, open a PR.

> **One gotcha worth naming.** If your `import scoutbot.typed_agent` fails with a message about
> `ANTHROPIC_API_KEY`, you bound a model to the `Agent` (either `Agent("anthropic:…")` or a `model=`
> argument). Remove it — the model belongs at *call time*, not construction. A key-free import is the whole
> offline design.

## Expected outcome (minimum requirements)

- [ ] **A Pydantic AI agent** with `output_type=TicketTriage` produces the same contract as `core.triage`
- [ ] **No bound model at import** — `Agent(output_type=…)` has no `model=`; the import needs no key
- [ ] **The real model is lazy** — `anthropic_model()` is only constructed at call time
- [ ] **An output validator** raises `ModelRetry` for a rule the type cannot express (owner is a handle)
- [ ] **Offline tests** drive the agent with `TestModel`/`FunctionModel` and set `ALLOW_MODEL_REQUESTS = False`
- [ ] **A retry test** with `FunctionModel` proves a bad-then-good reply recovers (call count is 2)
- [ ] **The whole earlier suite still passes** — the typed agent is additive
- [ ] Work is on a branch with an open pull request

## If you finish early

- **A second validator that carries domain knowledge.** Add a rule the type cannot say — e.g. a billing
  ticket may not be assigned to `technical-team`. Raise `ModelRetry` with a reason and test it with a
  `FunctionModel` that gets it wrong then right.
- **Swap `core.triage` for the typed agent in the graph.** Point `triage_ticket_node` at
  `typed_agent.triage` (patching `_client`-style seams becomes passing a `TestModel`). What breaks, what
  stays green, and what does the diff say about how well the contract was isolated?
- **A `FunctionModel` that inspects the prompt.** Have the function branch on the ticket text (return
  `billing` for a refund, `technical` for a crash) and write two asserts. Notice you are now testing your
  *prompt-shaping*, offline.
- **Structured output beyond triage.** Give the agent a richer `output_type` (add a one-line `rationale`
  field to a copy of `TicketTriage`) and confirm the schema, validation, and tests follow with no new
  plumbing.
- **Read what `retries` really does.** Set `retries=0` and watch the invalid-first `FunctionModel` test now
  raise instead of recovering. What is the production trade-off between more retries and failing fast?

## If you're running out of time

Protect steps 2–4 (the agent with no bound model, the lazy factory, `triage`) and steps 8–10 (the backstop,
the happy-path `TestModel` test, and the `FunctionModel` retry test). That core — a framework-held contract
that returns the same `TicketTriage`, proven offline with a real retry — is what the day is assessed on.
Trim the output validator (step 5) and the loud-failure/backstop tests (steps 11–12) first, but flag
whatever you skipped rather than quietly leaving it out. Do **not** bind a model to the `Agent` to save
time: a key-required import defeats half the day. (Coaches: see the coaches' page "Contingency plans" for
exactly what to prioritise.)
