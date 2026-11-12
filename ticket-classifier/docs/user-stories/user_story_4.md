# USER STORY 4: Parse a messy log file

Ticket T-2002 needs information from a log file to be resolved. Use code execution tool to extract a number out of a log file `sample_app.log`. The ticket explains what to look for.

## Steps

- check what options the code execution tool has
- add the code execution tool to ScoutBot
- make sure there are guardrails up (e.g. maximum execution time)
- the code should run in a sandbox
- ignore privacy concerns for now
- run the ticket and make sure it gets processed correctly
- docs: https://platform.claude.com/docs/en/agents-and-tools/tool-use/code-execution-tool

## Optional Goal 4.X: DO NOT DO THIS

Connect eval() to your agent. THIS IS VERY RISKY. DO NOT DO THIS. DO NOT DO THIS UNLESS YOU HAVE DISCUSSED YOUR SETUP OF A SANDBOX WITH COACHES. YOU MIGHT NOT WANT TO DO THIS AT ALL, BUT SOME OF YOU WILL LOOK UP THIS POSSIBILITY ANYWAY, SO WE HAVE TO COMMENT ON IT. BEFORE YOU EVEN THINK ABOUT IT, BACKUP YOUR PERSONAL DATA AND HIDE AWAY ALL CREDENTIALS. IF YOU DECIDE OTHERWISE WE TAKE NO LIABILITY.

- learn what the eval() function in Python does
- DO NOT COMBINE THIS WITH THE WEB SEARCH FUNCTION UNLESS YOU RUN IT ON A COMPUTER FAR FAR AWAY!
