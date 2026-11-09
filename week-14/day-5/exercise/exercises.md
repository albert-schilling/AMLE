# Week 14 · Day 5 — Graduation Presentation

Today you present an evidence-backed capstone story and submit the final graduation
artifacts. Your goal is not to sound production-ready. Your goal is to make precise claims,
show what supports them, and state what remains limited or unknown.

## Session settings

- **Presentation duration:** [PRESENTATION_MINUTES]
- **Feedback duration:** [FEEDBACK_MINUTES]
- **Audience / grouping:** [AUDIENCE / GROUP FORMAT]
- **Presentation order:** [PRESENTATION ORDER]
- **Submission location:** [SUBMISSION LOCATION]
- **Feedback capture:** [FEEDBACK CAPTURE METHOD]

## Deliverables

- graduation presentation;
- completed [Graduation Evidence Package](./graduation-evidence-package-template.md);
- completed [Final Rubric Self-Assessment](./final-rubric-self-assessment.md);
- stable links to the current capstone commit and evidence artifacts.

## 1. Build the graduation story

Use this sequence. Adapt the emphasis to your project; there is no canonical project.

1. **Problem and user**
   - Who is the intended user?
   - What problem or workflow are you addressing?
   - What outcome counts as success, and what is out of scope?
2. **Architecture**
   - What are the major components and boundaries?
   - How do data, context, models, tools, and state move through the system?
   - Which decisions mattered, and what trade-offs did you accept?
3. **Working end-to-end path**
   - Show one representative input reaching an observable outcome.
   - Identify the commit, environment, configuration, and dependencies.
   - Keep a fallback artifact ready for volatile steps.
4. **Evidence**
   - trace: what happened inside one representative run;
   - evaluation: how behavior was measured and against which threshold;
   - safety: which risks and controls were tested, including failures;
   - deployment: where and under what conditions the system ran.
5. **Limitations**
   - What remains untested, manual, fragile, expensive, slow, or unsafe?
   - Where is evidence thin or uncertain?
6. **Next steps**
   - Which next action most increases confidence or user value?
   - What evidence will show that it worked?

## 2. Use claim → evidence → limit

For every important claim, prepare three lines:

> **Claim:** The demonstrated workflow completes the intended support handoff.  
> **Evidence:** Run `…`, trace `…`, and eval rows `…` show the path under `…` conditions.  
> **Limit:** Offline dependency failures and peak-load behavior were not tested.

Avoid unsupported statements such as:

- “It is production-ready.”
- “The agent is safe.”
- “The system is reliable.”
- “The evaluation proves it works for everyone.”

Replace them with bounded claims that name the tested conditions and evidence.

## 3. Rehearse the working path

- [ ] Start from a representative input.
- [ ] Make the final outcome visible.
- [ ] Know which trace or log proves each important transition.
- [ ] Remove secrets and personal data from screens and artifacts.
- [ ] Use a stable test account or synthetic data where appropriate.
- [ ] Prepare a screenshot, recording, saved output, or trace as fallback.
- [ ] Label fallback evidence with its commit, date, and environment.
- [ ] Practice switching to fallback quickly and honestly.

If the live path fails, state what failed, show the strongest available evidence, and update
the limitation. Do not simulate a successful live run or present an old artifact as current.

## 4. Assemble the evidence package

Complete the package template. Every link should answer:

- What claim does this artifact support?
- Which commit/config/environment produced it?
- Can a reviewer open or reproduce it?
- What does it not establish?

Prefer a small navigable package over a large unlabelled artifact dump.

## 5. Complete the final rubric

Rate demonstrated evidence, not effort or intended future behavior. Each rating must cite a
specific package item. When evidence is mixed, choose the lower defensible rating and explain
the gap.

## Pace bars

### Minimum

- complete the six-part story;
- show or honestly fall back from one end-to-end path;
- include one trace and one evaluation artifact;
- name limitations and next steps;
- submit the evidence package and final rubric.

### Target

- connect each major claim to inspectable trace, eval, safety, and deployment evidence;
- include reproducibility metadata and stable artifact links;
- rehearse both live and fallback paths;
- make next steps follow directly from evidence gaps.

### Stretch

- navigate from claims to evidence live;
- quantify uncertainty, latency, cost, or operational trade-offs;
- add a compact reproduction guide;
- convert audience feedback into ranked follow-up evidence.

## 6. Present and capture feedback

Present for **[PRESENTATION_MINUTES]** and receive feedback for
**[FEEDBACK_MINUTES]**.

- **Audience / group format:** [AUDIENCE / GROUP FORMAT]
- **Presentation order:** [PRESENTATION ORDER]
- **Feedback capture method:** [FEEDBACK CAPTURE METHOD]

Capture feedback as:

| Feedback / question | Evidence requested | Response now | Follow-up priority |
| --- | --- | --- | --- |
| _…_ | _…_ | Answered / Partial / Unknown | Now / Next / Later |

Do not improvise certainty. “Unknown; here is how I would test it” is a valid response.

## 7. Submit

Submit to **[SUBMISSION LOCATION]**:

- evidence package;
- final rubric self-assessment;
- presentation or presentation link;
- current repository/commit link;
- any feedback follow-up required by the teacher.

Before submitting, verify links, permissions, commit identifiers, and removal of secrets.

## Troubleshooting

**“My live demo failed.”**
- Name the failure, switch to the labelled fallback, and avoid claiming the failed path
  worked live.

**“I do not have every kind of evidence.”**
- Submit the strongest current evidence, lower the affected rubric rating, name the gap, and
  write a testable next step.

**“My project is not production-ready.”**
- That is not required. Describe the environment and readiness level your evidence supports.

**“My architecture is different from other projects.”**
- Explain why it fits your problem, constraints, and evidence. There is no canonical design.

**“I have too many artifacts.”**
- Keep the evidence index concise. Link only artifacts that support a claim, limitation, or
  next step.
