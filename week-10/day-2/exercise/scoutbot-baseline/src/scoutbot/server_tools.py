"""ScoutBot's two Day 4 tools: `web_fetch` and `code_execution`.

Unlike `tools.py`'s two client tools, these are *server* tools - Anthropic's own
infrastructure runs them, this module never executes anything itself. There is no
`look_up_customer`-style Python function here to call: a server tool's definition is the
whole story on our side. See `loop.py` for how a server tool's result gets read back out
of the model's response (very differently from a client tool's).

`STATUS_PAGE_DOMAIN` is a real, public status page - Stripe's - standing in for "the
vendor's live status page" Dana asked about. Using a real domain means `allowed_domains`
is a genuine, testable restriction, not a placeholder that would break against the real
API.
"""
STATUS_PAGE_DOMAIN = "status.stripe.com"

WEB_FETCH_TOOL = {
    "type": "web_fetch_20250910",
    "name": "web_fetch",
    "max_uses": 3,
    "allowed_domains": [STATUS_PAGE_DOMAIN],
}

CODE_EXECUTION_TOOL = {
    "type": "code_execution_20250825",
    "name": "code_execution",
}

SERVER_TOOLS = [WEB_FETCH_TOOL, CODE_EXECUTION_TOOL]
