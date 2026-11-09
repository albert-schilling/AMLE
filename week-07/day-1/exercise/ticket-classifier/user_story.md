# User Story: 

As the Anchorpoint Support Team, we want a triage software that automatically prepares support requests from customers, so that they can be assigned to the right team and urgency.

Acceptance criteria:

- the triage service can be used by all team members
- tickets are read from a JSON file
- a LLM is used to create the ticket format from free text
- for each ticket, the service produces a category, a priority and the team it shall be assigned to
- the service can be run as a command-line program in Python