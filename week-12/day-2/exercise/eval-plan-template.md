# Capstone Evaluation Plan

> Fill in every section for **your own** agent, starting from yesterday's project brief. Keep it tight —
> this is a plan you could run against your v1, not an essay. Delete the _italic prompts_ as you replace
> them. When it is done, you should be able to read one golden row and your ship-if bar aloud and have
> them make sense to someone who has never seen your idea.

**Working title:** _your project name (same as the brief)_
**Author:** _your name_
**Date:** _today_

---

## 1. What we measure

> Copy your 2–3 success metrics from the Day 1 brief. Every eval below must trace back to one of these.
> If a metric here has no matching check later, or a check measures something the brief never promised,
> one of the two documents is wrong — reconcile them now.

| Success metric (from brief) | Kind | Target |
| --- | --- | --- |
| _e.g. task success rate_ | outcome | _e.g. ≥ 8 / 10_ |
| _e.g. answer correctness_ | quality | _e.g. ≥ 80%_ |
| _optional guardrail_ | guardrail | _e.g. < 5s p95_ |

---

## 2. Golden set

> A handful of real cases you can check by hand. **At least three rows**, and **at least one awkward,
> ambiguous, or refusal case** — not just happy paths. This is the eval you own and can verify yourself.

| # | Input (what the user sends) | Expected behaviour (what a good agent does) | Checks (how you score it) |
| --- | --- | --- | --- |
| 1 | _a real, typical input_ | _the good response_ | _fact / tone / format to verify_ |
| 2 | _another real input_ | _the good response_ | _…_ |
| 3 | _an **awkward** one: edge case, ambiguous, or should-refuse_ | _the good response (which may be "decline")_ | _…_ |

---

## 3. Metric ladder

> Which of the five rungs does your v1 actually need? Mark each, cheapest first. Run the cheap ones often;
> batch the rich ones. A simple agent may live mostly on rungs 1, 2, and 5.

- [ ] **1 · Smoke / structural** — it runs; output has the right shape. _(what shape?)_
- [ ] **2 · Deterministic correctness** — exact / regex checks on known answers. _(on which rows?)_
- [ ] **3 · Grounding** — did it cite, and is the citation real. _(if your agent retrieves)_
- [ ] **4 · Judge quality** — LLM-as-judge, scored 1–4 (see section 4).
- [ ] **5 · Outcome / task success** — did it do the whole job, end-to-end. _(this rung carries the bar)_

---

## 4. Judge rubric

> For output that is a matter of degree, an LLM-as-judge scores each **dimension** on the **1–4 scale**
> (1 fails, 2 weak, 3 good, 4 excellent — no neutral middle). Name your dimensions and, for each, say
> what a **3** looks like — concrete enough that two people would score the same answer the same.

| Dimension | What a **3 (good, shippable)** looks like |
| --- | --- |
| _correctness_ | _… facts are right and complete enough to act on_ |
| _grounding_ | _… claims are supported by a real source (if applicable)_ |
| _tone / safety_ | _… appropriate, and refuses what it should_ |

**Scale (fixed):** 1 = fails · 2 = weak · 3 = good, shippable · 4 = excellent.

---

## 5. Thresholds (ship-if bar)

> State the bar as a **number**. Fill in the blank. "Most of them should be good" is not a threshold.

> **Ship-if: ≥ \_\_\_ %** of golden rows score **≥ 3 on every dimension** (and all guardrails pass).

- **Guardrail bars (if any):** _e.g. p95 latency < 5s; cost < $0.02 / run_

---

## 6. Risks / failure modes

> The top few ways your agent could **fool this eval** — pass the bar while being wrong, or fail in a way
> the golden set does not cover. Name the check that would catch each.

- **Confident-but-wrong:** _how could it look right while being false? which check catches it?_
- **\<risk 2\>:** _e.g. right answer, no citation → a grounding check_
- **\<risk 3\>:** _e.g. fails on inputs outside the golden set → add a row_

---

### Self-check (before you hand it to a partner)

- [ ] Every metric in section 1 traces to a Day 1 success metric.
- [ ] **At least 3 golden rows**, including **at least one awkward / refusal** case.
- [ ] Metric ladder rungs marked for what your v1 needs.
- [ ] Judge rubric names its dimensions and says what a **3** looks like for each.
- [ ] A **ship-if threshold with a number** (not a vibe).
- [ ] Top **failure modes** named, each with the check that would catch it.
- [ ] You can read **one golden row** and your **ship-if bar** aloud and have them make sense.
