# Notes W8D3: interrupt and streaming

## Pause without a checkpointer (step 5)

`build_workflow()` with no checkpointer, high-priority ticket:

| Call | Result |
|---|---|
| `invoke(state)` | OK, returns state with `__interrupt__` |
| `invoke(state, config)` | OK, same |
| `get_state(config)` | `ValueError: No checkpointer set` |
| `invoke(Command(resume=...), config)` | `RuntimeError: Cannot use Command(resume=...) without checkpointer` |

The pause itself does not fail. The problem shows up only when you try to look at the
paused run or resume it. By then the paused state is gone, because nothing saved it.
The only way forward is to start over, which costs another model call.

## What re-runs on resume (step 7)

Two processes, same `thread_id`, file-backed `SqliteSaver`. Model mocked to count calls.

| | Process 1 (pause) | Process 2 (resume) |
|---|---|---|
| `node_get_customer` runs | 1 | 0 |
| `node_triage` model calls | 1 | 0 |
| `node_wait_for_human started` | 1 | 1 |

The node that paused runs again, from its first line. Everything before it does not.

Why: LangGraph checkpoints after each finished step (superstep). `node_get_customer` and
`node_triage` finished, so their outputs come from the checkpoint. `node_wait_for_human`
never finished: `interrupt()` raised and stopped it partway, so nothing it did was
saved. On resume, LangGraph starts that node again. This time `interrupt()` returns the
`Command(resume=...)` value instead of raising.

Consequence: any code above `interrupt()` in the same node runs twice. It must be cheap
and safe to repeat, so no model calls, emails or payments there.
