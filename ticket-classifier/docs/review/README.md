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

Suggested order: CLI crash (correctness 1), README, then split `classify` together
with passing settings explicitly (architecture 1 and 2).

Items already tracked in [../TODO.md](../TODO.md) are only referenced here.
