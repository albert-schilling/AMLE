# Week 12 · Day 4 — Exercise: Stand Up Your Capstone Skeleton

Today you write the first code of the capstone — but **no features.** You stand up the *foundation*: a
repo that runs from a clean clone, keeps secrets out, emits a trace on a no-op run, wires one real tool,
and passes one offline test. You build it **from scratch**, in whatever stack your architecture implies —
there is no starter repo to clone, because your project is yours.

**The rule for the whole day: get the skeleton green before you build a single feature.** A base that
runs, traces, and tests from the first commit means every later failure is a failure in the feature you
just added — not a "is it my code or my setup?" tangle.

**Deliverable:** a running skeleton repo meeting the [acceptance checklist](./foundation-setup-checklist.md).

**Time:** ~25 minutes in class (most people won't finish all six criteria — that's expected). **In-class
bar:** "runs from a clean clone" + "a no-op emits a trace." The tool + offline test can finish by end of
day.

**You need:** your [architecture design](../day-3/exercise/architecture-template.md) (it names your first
tool and parts), a working local dev environment, and any API key your first tool requires (in a `.env`,
never committed).

---

## Instructions

Build in this order — **each step green before the next.** Committing after each green step gives you a
working state to fall back to.

1. **Stand up a clean repo.** Minimal structure (an entrypoint, a place for tools/tracing/tests), pinned
   dependencies, and a `.gitignore` from the first commit. Put any secrets in a `.env` that is gitignored.
   - **Done when:** a *fresh clone* installs and runs with no errors. Test it by cloning into a new folder.

2. **Make the entrypoint run inside a sandbox.** Your minimal entrypoint can be an **echo** (input →
   nothing → same output). Ensure tool/generated-code execution is isolated from your host, files, and
   secrets — scaled to your tool's risk (a read-only HTTP call needs little; a code-runner needs real
   isolation).

3. **Emit a trace on the no-op run.** Wire observability *now*, before any real behaviour. The echo run
   should produce one readable trace with a span (or structured log line) per step: receive input, agent
   step, return output. **Look at the emitted trace** — if it's clean on an echo, it'll be clean on real
   steps.

4. **Wire one real tool.** The first tool your architecture named, behind a clean boundary (a custom
   function or an MCP tool). Start read-only where you can.

5. **Write one offline test.** Test the tool path with a **fake injected** in place of the real tool — no
   network, no API key. One call, one assertion. If you can't fake your tool, it isn't behind a boundary
   yet — fix that first, and the test falls out easily.

Unsure what your entrypoint or first tool should be? See the **"your stack may vary" matrix** in the
[checklist](./foundation-setup-checklist.md).

---

## Expected outcome (minimum requirements)

Judged against the [acceptance checklist](./foundation-setup-checklist.md). By end of day, **all** should
hold:

- [ ] Runs from a clean clone; dependencies pinned.
- [ ] Secrets in `.env`, gitignored, nothing committed.
- [ ] A no-op run emits a readable trace.
- [ ] One real tool is wired behind a clean boundary.
- [ ] One offline test passes with a fake injected (no network).
- [ ] Tool execution is contained (isolation scaled to risk).

**In-class minimum:** the first *and* third boxes (clean-clone run + no-op trace).

---

## Troubleshooting (the common blockers)

Work top to bottom — these are the failures that eat the most time.

**"It runs for me but not from a clean clone."**
- A dependency isn't pinned, or a needed file isn't committed. Pin everything (lockfile / pinned versions)
  and check `git status` for untracked files your app needs. Re-test by cloning into a *new* directory.

**"My secrets / `.env` aren't loading."**
- Is `.env` in the repo root (or wherever your loader looks)? Is it actually being loaded at startup? Is
  the process running from the directory you think it is? Print the loaded value's *presence* (not the
  value) to confirm. And confirm `.env` is in `.gitignore` **before** your first commit.

**"I committed a key by mistake."**
- Rotate the key now (assume it's compromised). Then remove it from the working tree, add `.env` to
  `.gitignore`, and — if it's already in history — scrub it (e.g. `git filter-repo`) or, for a fresh repo,
  consider starting the history clean. Prevention beats cure: `.gitignore` from commit one.

**"My no-op run doesn't produce a trace."**
- Start simpler: a structured log line with a run id and one line per step *is* a trace for today. Make
  sure tracing is initialised at startup and that the echo path actually goes through the traced code.

**"I can't write an offline test — it needs the real API."**
- That means the tool isn't behind a boundary yet. Put the tool behind a small interface, then inject a
  fake implementation in the test. The test should never touch the network.

**"My sandbox is turning into a big infrastructure project."**
- You've over-scoped it. Match isolation to risk: a read-only HTTP tool needs little more than keeping
  secrets out of its scope. Save heavy isolation (containers, restricted runners) for tools that execute
  model-generated code.

---

## If you finish early

Both are bridges to Friday, not extra scope:

- **Assert the trace** — extend your offline test to check the no-op run emitted the expected spans, so
  your observability is itself under test.
- **Write your slice's fake** — set up the fake for the *one golden row* Friday's vertical slice will
  target, so tomorrow you start by making a test go green.

> Do **not** start building Friday's feature today. The base has to be solid before anything sits on it —
> protect the skeleton, and tomorrow's slice goes in fast.
