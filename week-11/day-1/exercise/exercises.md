# W11D1 Exercise — Split ScoutBot Into a Team

## Scenario

For four weeks ScoutBot has been *one* agent. Week 10 Day 5 wired every capability into a single
`resolve_ticket` run, and it works — but one agent doing everything has a ceiling. The prompt grows, the
tools blur together, and a change to the refund path risks the order path. Anchorpoint's support volume is
climbing, and Priya wants each kind of ticket handled by a focused specialist she can change and test on its
own.

Today you split the monolith. You will build an **orchestrator** that classifies a ticket and dispatches it
to one of three **specialist workers** — refund, order, research — each its own subgraph. The orchestrator
decides *who* works; the specialist does the work. This is the **orchestrator-worker** pattern, the first of
the three multi-agent topologies (the other two — supervisor and swarm — you meet on the slides, and build a
supervisor as a stretch goal).

The point of today is *topology*, not new capability: every worker reuses a piece ScoutBot already owns
(the refund rules table, an order lookup, the retrieval index), so you spend your time on the shape of a
team, not on re-implementing tools.

## Starting point

`scoutbot-baseline/` is **the finished Week 10 agent** — the fully composed stack. Everyone extends this
same baseline, in place. Three things to know:

- **The router is a pure function.** `route_to_specialist(state) -> "refund" | "order" | "research"` is a
  plain function of state, so you can unit-test it with a hand-made dict and no graph — the same property
  Week 8 Day 2's routers had.
- **A worker is a subgraph that shares state by key.** Each specialist is its own small `StateGraph`,
  compiled and added to the parent as one node. It reads and writes the same state keys, so the customer
  looked up once at the top is visible to whichever specialist runs.
- **Don't share a reducer channel into a worker.** A compiled subgraph re-emits every channel it holds, so
  a worker that writes the parent's `operator.add` transcript makes the parent count those steps twice. Keep
  the transcript at the orchestrator level; give workers their own plain `finding`/`answer` channels.

## Your task

Working in pairs, on a new branch. **No new dependency today** — this is all LangGraph primitives you
already have.

### Part 1 — The shared state and the orchestrator (`src/scoutbot/orchestrator.py`)

1. **Define `TeamState`.** A `TypedDict` with the ticket inputs (`ticket_id`, `ticket_text`, `customer_id`,
   `refund_amount`), a `customer` dict, the dispatcher's `specialty`, a `finding` dict (a worker's
   intra-subgraph hand-off), an `answer`, and a `transcript` annotated `Annotated[list, operator.add]` so
   each orchestrator-level node *appends* rather than overwrites.
2. **Write the orchestrator nodes.** `look_up_customer_node` (fetch the customer once, at the top, via an
   injectable `get_customer`), and `dispatch_node` (classify the ticket into a specialty via an injectable
   `classify`, defaulting to a keyword rule `classify_specialty`). The dispatcher does *no* work — it only
   decides who works.
3. **Write the router.** `route_to_specialist(state) -> str` returns the specialty name, defaulting to
   `research` if unsure. Keep it a pure function.
4. **Add a `finalize` join node.** Every worker rejoins here, so anything that must happen once per ticket
   is written once (mirrors the Day-4 graph's `send_reply` diamond).

### Part 2 — The specialist workers (subgraphs)

5. **Build three worker subgraphs**, each a two-node `StateGraph` (`investigate` then `respond`) compiled
   and returned. **Give the workers their own `WorkerState`** with only the plain channels they touch
   (`ticket_text`, `customer`, `refund_amount`, `finding`, `answer`) — *not* the `transcript` reducer.
   - **refund**: `investigate` applies `policy.decide_approval` to the amount + customer facts and writes a
     `finding`; `respond` turns it into the customer-facing answer. No model.
   - **order**: `investigate` pulls the `ORD-XXXX` id out of the ticket (a regex) and looks up its status
     via an injectable `get_order_status` (default: read `mock_orders.json`); `respond` composes the answer.
   - **research**: `investigate` calls an injectable `kb.search(...)` (default: the lazy process index) and
     writes the passages; `respond` grounds the answer with `format_passages`, or declines if nothing hit.
6. **Wire the orchestrator.** `orchestrator_builder(...)` builds a `StateGraph(TeamState)`, adds the
   `look_up_customer` and `dispatch` nodes, adds each compiled worker subgraph as a node, and connects them:
   `START -> look_up_customer -> dispatch`, then `add_conditional_edges("dispatch", route_to_specialist,
   {...})` to the three workers, then each worker `-> finalize -> END`.

### Part 3 — A demo and offline tests

7. **See it work (`run_orchestrator.py`).** Build the orchestrator with real defaults and run three tickets
   — a refund, an order, and a policy question — printing the route, the transcript, and the answer for
   each. Watch `look_up_customer` run once, `dispatch` pick a specialty, exactly one worker fire, and every
   route end at `finalize`. **This needs no API key.**
8. **Test the pure functions (`tests/test_orchestrator.py`).** `classify_specialty` (refund/order/research,
   and refund-beats-order when both appear), `route_to_specialist` (including the `research` fallback), and
   `dispatch_node` — all with hand-made dicts, no graph.
9. **Test each worker subgraph directly.** Invoke a compiled worker with a hand-made state and a *stub*
   collaborator (a dict-backed `get_customer`, a stub `get_order_status`, a `StubKB` with a fixed hit list),
   and assert on `finding` (proves `investigate` ran) and `answer` (proves `respond` ran). No embedder, no
   network.
10. **Test the whole orchestrator end to end.** With every collaborator stubbed, assert a refund ticket
    routes through the refund worker, an order ticket through the order worker, a research ticket through the
    research worker, and that the transcript reads `look_up_customer -> dispatch->X -> finalize`.
11. **Same habit as every day**: keep the Week 10 suite green, commit on your branch, open a PR.

> **One gotcha worth naming.** If your worker writes to the `transcript` reducer channel, run the
> orchestrator and print the transcript: you'll see the earlier steps counted twice. That's the shared-
> reducer trap. The fix isn't to remove the reducer — it's to keep it out of the worker's state schema so
> the subgraph never re-emits it.

## Expected outcome (minimum requirements)

- [ ] **`TeamState`** with a reducer `transcript` and plain `finding`/`answer` channels
- [ ] **An orchestrator** that looks the customer up once, dispatches, routes to one worker, and finalizes
- [ ] **`route_to_specialist` is a pure function** — tested with a hand-made dict, no graph
- [ ] **Three worker subgraphs**, each `investigate -> respond`, each reusing an existing ScoutBot piece
- [ ] **Workers own plain channels, not the transcript reducer** — no double-counting in the run log
- [ ] **Every collaborator is injectable** (`get_customer`, `classify`, `get_order_status`, `kb`) so the team
  runs offline
- [ ] **`run_orchestrator.py`** routes three tickets to three specialists, with no API key
- [ ] **Offline tests**: routers/classifier (pure), each worker (stubbed), the whole orchestrator end to end
- [ ] **The Week 10 suite still passes** — the day is additive
- [ ] Work is on a branch with an open pull request

## If you finish early

- **Make the dispatcher smart.** Swap the keyword `classify_specialty` for a model-backed classifier
  (inject it as `classify`). Find a ticket the keyword rule mis-routes — e.g. *"how long do refunds take?"*
  is a policy question, but the word "refund" sends it to the refund worker — and show the model gets it
  right. What did you give up (latency, cost, a key) to get that?
- **Build the supervisor variant.** Instead of a router that picks *one* worker, write a `supervisor` node
  that returns `Command(goto=..., update=...)` and hands out work from a `plan` list, with each worker
  reporting back to it. Now a ticket like *"check the policy, then handle the refund"* can visit two
  specialists in turn. Which topology fits which ticket?
- **Give a worker a third internal step.** Add a node inside the refund subgraph (say, a `log_decision`
  step) and confirm the orchestrator neither knows nor cares — that's the encapsulation a subgraph buys.
- **Name the swarm.** Sketch what "no orchestrator, peers hand off to each other" would look like here.
  Where would the control live, and what gets harder to test?

## If you're running out of time

Protect steps 1–4 (the orchestrator: state, dispatch, router, finalize) and step 5's **refund** worker (it
needs no external anything), then step 6 (wire them) and step 8 (the router/classifier tests). That
core — a ticket classified and routed to one specialist subgraph, proven by a pure-function router test — is
what the day is assessed on. The order and research workers (the rest of step 5) and their tests are the
first things to trim, and the supervisor is already a stretch goal. **Do not** skip giving workers their own
`WorkerState` (the shared-reducer trap): a transcript that double-counts is the one bug that will confuse
everyone downstream. Flag whatever you skipped rather than quietly leaving it out. (Coaches: see the
coaches' page "Contingency plans" for exactly what to prioritise.)
