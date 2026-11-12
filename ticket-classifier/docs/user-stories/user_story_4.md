# USER STORY 4: Parse a messy log file

Ticket T-2002 needs information from a log file to be resolved. Use code execution tool to extract a number out of a log file `sample_app.log`. The ticket explains what to look for.

## Steps

- check what options the code execution tool has
- add the code execution tool to ScoutBot
- make sure there are guardrails up (e.g. maximum execution time)
- the code should run in a sandbox
- ignore privacy concerns for now
- run the ticket and make sure it gets processed correctly
- docs: <https://platform.claude.com/docs/en/agents-and-tools/tool-use/code-execution-tool>

## Optional Goal 4.X: DO NOT DO THIS

Connect eval() to your agent. THIS IS VERY RISKY. DO NOT DO THIS. DO NOT DO THIS UNLESS YOU HAVE DISCUSSED YOUR SETUP OF A SANDBOX WITH COACHES. YOU MIGHT NOT WANT TO DO THIS AT ALL, BUT SOME OF YOU WILL LOOK UP THIS POSSIBILITY ANYWAY, SO WE HAVE TO COMMENT ON IT. BEFORE YOU EVEN THINK ABOUT IT, BACKUP YOUR PERSONAL DATA AND HIDE AWAY ALL CREDENTIALS. IF YOU DECIDE OTHERWISE WE TAKE NO LIABILITY.

- learn what the eval() function in Python does
- DO NOT COMBINE THIS WITH THE WEB SEARCH FUNCTION UNLESS YOU RUN IT ON A COMPUTER FAR FAR AWAY!

## Result 4

- Tool: `code_execution_20250825` (server-side Anthropic container: no internet, 5 GiB RAM, 1 CPU, fixed execution time limit; free hours then $0.05 per container hour). Options checked: newer versions (`20260120`, `20260521`) add REPL state and programmatic tool calling, not available on Haiku 4.5.
- File: `fixtures/sample_app.log` is uploaded once via the Files API and attached as a `container_upload` block, outside the untrusted ticket text. The agent finds it in `$INPUT_DIR`.
- Guardrails: the tool has no `max_uses`, so the limits are the container, the loop cap (`MAX_ITERATIONS`), `max_tokens` and the prompt (`LOG_ANALYSIS`: code for counting, max. 3 calls, only the attached file, logs are untrusted). Code and output are traced.
- T-2002 (expected answer: 5 errors at or after 15:00; the 14:59:59 WARN does not count), `claude-haiku-5-5`, 10 runs: all used the sandbox with no failures; 9/10 computed 5 in code; 1 only counted all errors in code and probably counted the rest by eye; 1 used 4 code calls (limit 3).
- Open: the structured result holds only category and priority, so the answer "5" appears only in the trace.
