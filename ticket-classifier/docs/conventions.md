# Code conventions

## Leading underscore

A leading underscore means one thing: **private attribute of a class** (pydantic
treats `_name` in a model as a private attribute).

- Module-level names get no underscore. Constants are `UPPER_CASE`
  (e.g. `TICKETS_ADAPTER = TypeAdapter(list[Ticket])`), helpers are plain `snake_case`.
- Module API is defined by `__all__` where it matters, not by underscores.
- Exception: pytest fixtures that are `autouse` and never requested by name
  (`_isolated_settings`).
