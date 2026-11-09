# W11D5 Exercise — EU AI Act Classification Memo

## Scenario

ScoutBot has come a long way. Over the last four weeks Priya turned it from a single
composed agent into a governed team: an orchestrator with specialist workers (Mon), a planner
that keeps cost and latency in check (Tue), an eval suite with an LLM-as-judge that proves
quality (Wed), and a defense-in-depth safety stack that scrubs, authorizes, validates, and
escalates (Thu). It runs in production, answering Anchorpoint's customer tickets about
refunds, orders, shipping, warranty, and billing.

This morning **Dana** (Priya's manager) forwarded an email from **Legal**:

> "The EU AI Act's headline deadline was 2 August 2026. I keep reading that it got *delayed*
> by something called the 'Digital Omnibus' — so do we actually need to do anything for
> ScoutBot right now, or can we stand down until 2027? Also: two of us can't agree on whether
> *we're* even the ones on the hook, since the model is Anthropic's, not ours."

Dana wants a short, honest classification memo before she replies — not legal advice, but an
engineer's clear-eyed read of where ScoutBot sits and what that means in practice. She also
mentions, almost in passing, a product idea she's been floating: having ScoutBot decide **which
customers qualify for Anchorpoint's new "hardship" deferred-payment plan** — and she wants to
know if that would change the answer.

## Starting point

There is **no starter code** for this exercise — today's deliverable is a **written memo**, not
a build. You'll need:

- Today's live lesson slides (the four-tier risk pyramid, the provider-vs-deployer chain, the
  Annex III domains, and the post-Omnibus timeline) — reference them directly.
- `memo-template.md` in this folder — the scaffold your memo should follow.

You are classifying a system, not writing law. Where you hit a genuinely legal judgment call,
the right move is to *name it as one for Legal to confirm*, not to guess with false confidence.

## Your task

Individually or in pairs:

1. **Classify ScoutBot today.** Which of the four risk tiers (unacceptable / high-risk /
   limited-transparency / minimal) does it fall into, and *why*? Ground the "why" in what
   ScoutBot actually does, not in how sophisticated it is.
2. **Name the obligation that applies now, and by when.** If ScoutBot lands in the
   limited-transparency tier, what concrete thing must Anchorpoint do, under which article, and
   from what date? Answer Legal's "can we stand down?" question honestly using the timeline.
3. **Settle the provider-vs-deployer question.** Who is the *provider* and who is the *deployer*
   here — and where does Anthropic (whose model ScoutBot is built on) sit? State who carries the
   obligation you named in step 2.
4. **Assess Dana's proposed change.** If ScoutBot starts deciding who qualifies for the
   deferred-payment plan, does its risk tier change? Say which Annex III domain (if any) that
   use would touch, and what *new* obligations would follow if it became high-risk.
5. **Flag what you'd escalate to Legal.** Name one or two judgment calls you are *not* qualified
   to make alone and would want a lawyer to confirm before Anchorpoint acts.
6. Fill in `memo-template.md` with your answers and save it as `memo.md` in this same folder.

## Expected outcome (minimum requirements)

- [ ] A single, clearly stated risk tier for ScoutBot **today**, justified by what it does
- [ ] The specific present-day obligation named (article + plain-English action + date), with a
      correct, honest answer to "was it delayed?"
- [ ] Provider and deployer identified for ScoutBot, and Anthropic's separate role named
- [ ] A reasoned verdict on whether the deferred-payment-plan change tips ScoutBot into
      high-risk, naming the relevant Annex III domain
- [ ] At least one honest "escalate to Legal" judgment call
- [ ] Saved as `memo.md`, following `memo-template.md`'s structure

## If you finish early

- Write the one-sentence AI-disclosure line you'd actually put in ScoutBot's chat window to
  satisfy the transparency obligation — then argue whether your current UI already makes it
  "obvious from the context" (the Article 50 exception) or not.
- Name one *other* plausible product change that would push ScoutBot into a *different* Annex III
  domain than the payment-plan one, and say which domain.

## If you're running out of time

It's fine to submit a rough draft today (tier + the one present-day obligation + provider vs
deployer) and finish the "proposed change" and "escalate to Legal" sections before the next
session — flag what's incomplete rather than leaving it unstated. (Coaches: see the coaches'
page "Contingency plans" for exactly what to prioritise.)
