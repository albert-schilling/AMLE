# Snippets for Review

## Router

```python
def route_after_triage(state: TicketState) -> str:
    """Pick the next node from the triage result: high priority goes to a human."""
    return "wait_for_human" if state["triage"]["priority"] == "high" else "mark_handled"
```

## Routing Targets

Nodes targeted by a router.

```python
def wait_for_human_node(state: TicketState) -> dict:
    """Terminal node: record that a person needs to look at this ticket."""
```

```python
def mark_handled_node(state: TicketState) -> dict:
    """Terminal node: record that ScoutBot handled this ticket itself."""
    return {"outcome": "handled", "notes": ["handled by ScoutBot"]}
```

## Conditional Edges

```python
    builder.add_conditional_edges(
        "triage_ticket",
        route_after_triage,
        # The path map is not required if the return value matches the designated nodes' names.
        {
            "wait_for_human": "wait_for_human",
            "mark_handled": "mark_handled"
        },
    )
```

## Checkpoint

```python
    builder.compile(checkpointer=InMemorySaver())
```

```python
    # Running the graph

    # One thread per ticket: 
    # the thread_id is the key its checkpoints are stored under.
    config = {"configurable": {"thread_id": ticket["id"]}}

    for mode, chunk in graph.stream(state, config, stream_mode=["updates", "values"]):
        ...

    # Retrieve and print the saved state from the checkpointer.
    snapshot = graph.get_state(config)
```

Installing the SQlite Checkpointer:

`uv add langgraph-checkpoint-sqlite`

```python
    # Create a database connection.

    CHECKPOINT_DB = Path(__file__).parent / "checkpoints.db"

    connection = sqlite3.connect(
        CHECKPOINT_DB,
        # Allow multiple threads, in this case workflow runs, use the same database connection.
        # SqliteSaver handles the thread-safety (who is allowed to access the DB)
        check_same_thread=False
        )
```

```python
    builder.compile(checkpointer=SqliteSaver(connection))
```

## Resume from Checkpoint

```python
    # Test if there is an unfinished run in the database.
    # If there is the initial state must be None,
    # otherwise a new run will be started. 
    if graph.get_state(config).next:
            state = None
        else:
            state = create_initial_state(...)

    for mode, chunk in graph.stream(
        state, config, stream_mode=["updates", "values"], 
        # Block the execution of the next node until the state is saved.
        # Setting this to async will save the state,
        # while the next node already runs.
        durability="sync"
    ):
```

## Tests

### Router Tests

```python
def test_router_sends_high_priority_to_a_human():
    assert route_after_triage({"triage": {"priority": "high"}}) == "wait_for_human"

def test_router_lets_scoutbot_handle_everything_else():
    for priority in ("low", "medium"):
        assert route_after_triage({"triage": {"priority": priority}}) == "mark_handled"
```
