# Week 13 · Day 3 — Capstone Midterm Review

> **Half-day scope:** These materials cover only the capstone review half. The standing
> Career Session is separate and is not authored here.

## Teacher-configured logistics

- Presentation: `[PRESENTATION_MINUTES]` minutes
- Feedback: `[FEEDBACK_MINUTES]` minutes
- Audience / group format: `[AUDIENCE / GROUP FORMAT]`
- Submission location: `[SUBMISSION LOCATION]`
- Feedback capture method: `[FEEDBACK CAPTURE METHOD]`

## Deliverables

- completed [Midterm Review Package](./midterm-review-template.md);
- completed [Feedback Log](./feedback-log-template.md);
- revised top-three priorities for Thursday and Friday.

## 1. Prepare one evidence-based path

Choose one representative input from your golden set. Your review should connect:

1. current problem and scope;
2. architecture as currently built;
3. one real run from input to output;
4. the trace explaining that run;
5. one eval result and threshold;
6. one known limitation;
7. the next engineering decision.

Do not narrate every feature. A smaller, inspectable path is stronger than unfinished
breadth.

## 2. Prepare a demo fallback

Live dependencies can fail. Bring one real, recent fallback:

- a recorded run;
- saved trace;
- fixture or offline mode;
- screenshot of output/evidence;
- cached non-sensitive artifact.

The fallback must show actual current behavior, not a fabricated mockup.

## 3. Rehearse to the configured time

Fit the review into `[PRESENTATION_MINUTES]` minutes. Protect these beats if time is tight:

- working path;
- trace and eval;
- known limitation;
- next decision.

Remove background detail before removing evidence.

## 4. Present and capture

Run the review in `[AUDIENCE / GROUP FORMAT]`.

During `[FEEDBACK_MINUTES]` minutes of feedback:

- capture observations using `[FEEDBACK CAPTURE METHOD]`;
- ask short clarifying questions;
- do not accept or reject every suggestion live;
- avoid exposing credentials or sensitive trace/context content.

## 5. Classify feedback

After the review, classify each item:

- **fix now** — confirmed, urgent, in scope;
- **investigate** — useful signal requiring evidence;
- **defer** — valid, lower priority, with a future trigger;
- **decline** — out of scope or unsupported, with rationale.

Then choose exactly three revised priorities. Each must cite a failed eval, trace finding,
known risk, or confirmed feedback signal.

## Submission

Submit the review package and feedback log to `[SUBMISSION LOCATION]`.

## Troubleshooting

**“My full workflow is not complete.”**
- Show the strongest real path, state its current boundary, and name the top limitation.
  The review measures evidence and judgment, not feature count.

**“The live integration may fail.”**
- Use the prepared fallback and explain the dependency. Keep a real trace/eval available.

**“My eval is red.”**
- Show it honestly. Explain the threshold, likely cause, and decision it triggers.

**“The architecture diagram is outdated.”**
- Update it to the system as built. The review should not orient people with an abandoned plan.

**“I received conflicting feedback.”**
- Record both, classify as investigate, and define the evidence needed to decide.

**“A reviewer suggested a large new feature.”**
- Compare it with scope and evidence. Defer or decline unless it addresses a confirmed,
  high-value risk.

**“I have too much to say.”**
- Remove implementation chronology and feature inventory. Keep frame, architecture, one run,
  evidence, limitation, and decision.
