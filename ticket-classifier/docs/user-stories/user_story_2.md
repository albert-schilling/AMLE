# User Story 2

As a Support Team, we want the AnchorPoint support agent to look up customer info, so that it can produce more accurate classifications and draft a reply.

## Exercise
- design a data model for customers. What fields should they have?

## Criteria

- implement the data model as a Pydantic class
- you do not have access to the real data
- create artificial data as a JSON file
- add some customer id to the example support requests, sometimes it might be empty 
- create a tool that looks up customer data
- add the tool to the agent