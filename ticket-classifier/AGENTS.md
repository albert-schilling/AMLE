# Agent instructions

Ticket classifier: a LangGraph workflow that triages support tickets with Claude and
pauses high-priority ones for a human. Module map: the Layout table in
[README.md](README.md). Code rules: [docs/conventions.md](docs/conventions.md).

## Commands

```sh
make test      # pytest; never calls the API
make lint      # ruff check
make format    # ruff format
```

- Run `make lint`, `make format` and `make test` after every change.
- `make run`, `make approve` and `make decline` use real data, and `make run` calls the
  Anthropic API (costs money). Never run them without asking.
- `make reset` deletes saved runs; paused tickets are lost. Ask first.

## Git

- Never commit, push, create branches or open PRs unless explicitly asked, or after
  asking first.
