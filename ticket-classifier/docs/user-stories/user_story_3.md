# USER STORY 3: Web Fetch of a live status page

As the billing team, we want to have Scoutbot make sure that the payment provider (Stripe) is running before assuming a duplicate charge is Anchorpoint's fault.

## Steps

- connect to "status.stripe.com"
- use the web page max. 3 times per ticket
- make sure there are no incidents reported on the status page. The four categories "Global payments", "Revenue and finance automation", "Stripe core components" and "Banking as a service" need to be up.
- run the web fetch in a safe sandbox
- integrate the web fetch into the agent for billing issues. 
- include the guardrails on slide 9
- ignore privacy concerns for now
- sample ticket T-2001 needs the status check
- docs: https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool

## Optional Goal 3.1

- also try out the web_search tool in the antrophic documentation

## Optional Goal 3.2

- create fake payment data: client_id, invoice_number, amount and timestamp
- deploy it to a live web page using GitHub pages (HTML or JSON), see Settings
- access the page using the web_fetch tool and have the agent match the billing with client data
- should the matching of client data and billing info be done by an agent?

## Optional Goal 3.3

- implement a tool that does the web search yourself.
- use httpx.get()
- TAKE SAFETY PRECAUTIONS: RESTRICT THE WEB ACCESS TO A URL YOU KNOW
