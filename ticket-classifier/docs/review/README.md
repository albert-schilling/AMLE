# Code review (2026-11-13)

Review of code, structure, readability and architecture of `ticket-classifier`.
At review time: 104 tests pass, `ruff check` and `ruff format --check` are clean.

| File | Topic |
| --- | --- |
| [strengths.md](strengths.md) | What works well and should stay |
| [correctness.md](correctness.md) | Bugs and error handling |
| [architecture.md](architecture.md) | Module boundaries, dependencies, data flow |
| [readability.md](readability.md) | Naming, duplication, small cleanups |
| [docs-and-structure.md](docs-and-structure.md) | README, agent files, config checks |
| [temporary-implementations.md](temporary-implementations.md) | Exercise code, fake data and stand-ins |

Done or decided: CLI crash accepted (correctness 1), `classify` split (architecture 1),
settings singleton kept (architecture 2). Next: README update (docs-and-structure).

Items already tracked in [../TODO.md](../TODO.md) are only referenced here.
