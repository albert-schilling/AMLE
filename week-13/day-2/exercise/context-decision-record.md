# Context Decision Record

**Project / repo:** _…_
**Primary workflow:** _…_
**Representative input or golden row:** _…_
**Selected strategy:** Retrieval / Workflow state / Short-term context / Durable memory / None
**Date:** _…_

---

## 1. Required behavior

What correct answer or action cannot happen from the current input alone?

_…_

What specific information changes the behavior?

_…_

If no additional information is required, explain why **none** is the simplest correct
strategy:

_…_

## 2. Classification

- [ ] **Source knowledge:** facts outside the current run
- [ ] **Workflow state:** where this process is now
- [ ] **Short-term context:** what this session has established
- [ ] **Durable memory:** what must survive for future sessions
- [ ] **None:** the input and live tool results are sufficient

Why does this classification fit better than the alternatives?

_…_

## 3. Context boundary

- **Source/store:** _where the information comes from_
- **Owner/scope key:** _user, run, session, task, tenant, or other_
- **Allowed reads:** _…_
- **Allowed writes:** _…_
- **Expiry/deletion rule:** _…_
- **Sensitive data excluded or redacted:** _…_
- **Trace metadata (not raw secrets):** _operation, scope, result count, latency, etc._

## 4. Proof

### Positive case

- **Input:** _…_
- **Context fixture:** _…_
- **Expected changed behavior:** _…_
- **Eval/check:** _…_

### Isolation / negative case

- **Different user, run, session, task, irrelevant item, or expired item:** _…_
- **Expected absence:** _what must not affect or appear in the output_
- **Eval/check:** _…_

## 5. Evidence and status

- **Selected pace bar:** Minimum / Target / Stretch
- **Trace/run identifier:** _…_
- **Positive result:** _…_
- **Isolation result:** _…_
- **Green commit:** _…_
- **Known limitation:** _…_
- **Exact next step:** _…_
