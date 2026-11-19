# Notes

## Dictionary like data types in Python

**When to use which here:**

| Tool | Use for | In this project |
|---|---|---|
| plain `dict` / `list` | short-lived, local values | stream chunks, the `fields` in `to_classified_ticket` |
| `TypedDict` | must stay a real dict at runtime, but typed | `TriageState` (LangGraph wants dicts), `HumanAnswer` (stored in checkpoints) |
| `dataclass` | internal objects, no validation needed | `BatchResult`, `RunArgs`, `ResumeArgs` |
| pydantic `BaseModel` | data from outside: validate and parse JSON | `Ticket`, `Customer`, results, model output |