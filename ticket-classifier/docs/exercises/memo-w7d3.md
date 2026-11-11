# Framework Evaluation Memo

**To:** Dana
**From:** Albert
**Re:** Agent framework options for ScoutBot's next phase

## The two frameworks I'm comparing

- Framework A: Anthropic SDK
- Framework B: LangGraph

Both frameworks are from different quadrants of the landscape grid.
The Anthropic SDK is a thin rapper around the Anthropic API for model calls.
LangGraph is a full grown orchestration framework to create stateful, long-running agents or multi-agent workflows.  

## Comparison

| | Anthropic SDK | LangGraph |
| --- | --- | --- |
| What it adds beyond a hand-rolled loop | tool runner, streaming, async, batch processing, file uploads | multi-agent workflows (graphs, orchestration patterns), persistence, memory and state, human in the loop, time-travel (checkpoints, replay and fork) |
| New complexity / vocabulary it introduces | SDK specific interfaces | graph architecture, orchestration patterns |
| Fit for "more reliable escalation" | no built-in functionality (probably less control than with a hard-coded workflow) | built-in |
| Fit for "eventually several specialist bots" | no built-in support for this | yes (one of the typical orchestration patterns LangGraph supports) |

## Recommendation

For Dana's need of an eventual multi-bot specialization I recommend LangGraph because orchestrating multiple agents in a well defined workflow or pattern is exactly what LangGraph is made for.

The Anthropic SDK does not support this. We would have to build our own orchestration wrapper around two instances of an Anthropic client.

## What I'd want to prototype first

Before Anchorpoint actually commits to this, I'd want to check:

1. The complexity of implementing a human escalation and a multi-agent workflow with LangGraph.
2. The adoption, update rate, health and security risk of LangGraph.
3. The compatibility of LangGrahp with the providers and models we would like to use.

## If I finished early (optional)

- What would ScoutBot's tools/roles be called under my recommended framework?
There would probably still be a get_customer tool and an escalate tool. The escalate tool would be wrapped by the HITL middleware (Human in the Loop). So its execution can be denied by a user, effectively denying or negating an escalation.
- The strongest honest counter-argument for the framework I didn't pick:
There is a learning curve. We have to first understand and later maintain the use of LangGraph. The framework's APIs might change over time, they might have security issues that require us to update to newer versions. 
