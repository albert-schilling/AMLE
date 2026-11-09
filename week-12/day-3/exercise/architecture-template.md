# Capstone Architecture Design (one page)

> Fill in every section for **your own** agent, starting from your project brief. Keep it to one page —
> this is a blueprint someone else could build from, not a spec document. Delete the _italic prompts_ as
> you replace them. When it is done, you should be able to walk a partner through the diagram, from user
> input to grounded output, in a few sentences.

**Working title:** _your project name (same as the brief)_
**Author:** _your name_
**Date:** _today_

---

## 1. Topology + why

> The overall shape of the system, from the four you met in Week 11. **Default to a single agent.** Every
> extra agent is a cost — more parts, more failure modes, more to trace — so justify it in one sentence or
> drop it to a stretch goal.

- **Chosen topology:** _single agent · orchestrator-worker · supervisor/router · swarm/peer_
- **Why it fits (one line):** _…_
- **If more than one agent — the one sentence that justifies it:** _what does the second agent do that one
  agent with a tool could not?_

---

## 2. System diagram

> Draw a **block diagram** of your agent (on paper, a whiteboard, or any tool — then paste/link it here).
> Use the convention from class:

```
                 ┌─────────────────┐
                 │   User input    │
                 └────────┬────────┘
                          │
   ┌──────────────┐  ┌────┴─────────┐  ┌──────────────┐
   │  Memory /    │──│  Agent core  │──│  Tools / MCP │
   │  retrieval   │  │ model + loop │  │              │
   └──────────────┘  └────┬─────────┘  └──────────────┘
                          │            (+ state on the core)
                 ┌────────┴────────┐
                 │ Grounded output │
                 └─────────────────┘

   [ Observability / tracing: every step is traced, end to end ]
```

> Replace the sketch above with **your** version — keep only the parts your agent actually has.

**My diagram:** _paste an image, a link, or your own ASCII block diagram here_

---

## 3. Components

> Name each standard part **for your project**. Write "none (why)" for any your v1 genuinely does not need
> — an absent part is a deliberate choice, not a hole.

| Component | For my agent, this is… |
| --- | --- |
| **Model + loop** | _which model; single-shot or a loop_ |
| **Tools / MCP** | _the external system(s) it calls_ |
| **Memory / retrieval** | _what it reads or remembers (docs, vectors, history)_ |
| **Durable state** | _what it must keep between steps (or "none — why")_ |
| **Observability** | _what you trace, and where traces go_ |

---

## 4. Trace to a week

> Label every box on your diagram with the week that taught it. Anything you **cannot** place goes in
> section 5 — it is either unnecessary, or a decision you still owe.

| Box on my diagram | Learned in… |
| --- | --- |
| _e.g. agent loop_ | Week 7 |
| _e.g. tool / MCP call_ | Weeks 7 + 10 |
| _e.g. durable state / tracing_ | Week 8 |
| _e.g. retrieval_ | Week 9 |
| _e.g. multi-agent topology_ | Week 11 |

---

## 5. Open decisions

> The boxes you could not trace, and anything you still need to decide before Thursday. A design with
> **zero** open decisions on Wednesday is usually hiding them.

- _… — how/when you'll decide it_
- _… — how/when you'll decide it_

---

### Self-check (before you walk a partner through it)

- [ ] A **topology** is chosen and justified in one line (and any extra agent has its one sentence).
- [ ] A **one-page block diagram** exists: user → agent core → tools/retrieval → grounded output.
- [ ] **Every component** is named for your project (or marked "none — why").
- [ ] **Each box traces to a week** — nothing is invented from nothing.
- [ ] **Open decisions** are listed honestly.
- [ ] Nothing in the diagram is a part your **v1 does not need** (it matches the brief's scope).
- [ ] You can **narrate the flow** from input to output in a few sentences.
