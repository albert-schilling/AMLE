# Agent instructions

Ticket classifier: a LangGraph workflow that triages support tickets with Claude and
pauses high-priority ones for a human. Module map: the Layout table in
[README.md](README.md). Code rules: [docs/conventions.md](docs/conventions.md).

## Commands

```sh
make test            # pytest; never calls the API, no database
make test-db         # tests against PostgreSQL (needs make db-up)
make test-embedding  # the one test with the real embedding model
make lint            # ruff check and mypy (strict, src only)
make format          # ruff format
```

- Run `make lint`, `make format` and `make test` after every change. After a change
  in `knowledge/` or to SQL, also run `make test-db`.
- `make run`, `make approve` and `make decline` use real data, and `make run` calls the
  Anthropic API (costs money, two calls per ticket: triage and reply). Never run them
  without asking.
- `make reset` deletes saved runs; paused tickets are lost. Ask first.
- `make kb-index` and `make kb-eval` cost nothing (local model), but write to the
  `knowledge` database: `kb-eval` adds an index per chunk setting.
- Never print or copy secrets: `.env` and `database/.env` hold the API key and the
  database password.

## Git

- Never commit, push, create branches or open PRs unless explicitly asked, or after
  asking first.
