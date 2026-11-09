# ScoutBot (FINAL v3 - don't touch, it works)
#
# Handover notes from Jonas (last commit before he left):
#
#   Just run this top to bottom. It reads a support ticket, asks the model what
#   category and priority it is, and prints the answer. Works great on my laptop.
#
#   — Jonas

import re

from anthropic import Anthropic

# TODO(jonas): rotate this before the security audit lol
client = Anthropic(api_key="sk-ant-REPLACE-ME-this-is-hardcoded-and-that-is-the-problem")

tickets = [
    "I was charged twice for my subscription this month and need a refund immediately - "
    "this is the third time this has happened and I'm considering cancelling.",
    "The export-to-CSV button on the dashboard has been spinning for 10 minutes and never "
    "finishes. I can't get my monthly report out.",
    "Hi, I'd like to update the email address on my account to a new one. Not urgent, just "
    "whenever you get a chance.",
]


def classify(ticket_text):
    prompt = (
        "You are a support ticket triage assistant. Reply in EXACTLY this format:\n"
        "Category: <billing|technical|account|other>\n"
        "Priority: <low|medium|high>\n\n"
        f"Ticket: {ticket_text}"
    )
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    reply = response.content[0].text
    print("Raw reply:", reply)

    # this "works" as long as the model replies in exactly the format we asked for...
    category_match = re.search(r"Category:\s*(\w+)", reply)
    priority_match = re.search(r"Priority:\s*(\w+)", reply)
    category = category_match.group(1) if category_match else None
    priority = priority_match.group(1) if priority_match else None
    return category, priority


if __name__ == "__main__":
    for t in tickets:
        category, priority = classify(t)
        print(t[:50], "->", category, priority)
        print("---")

# Works on my machine! There's no repo for this - this script *is* the deployment. — Jonas

# # this "works" as long as the model replies in exactly the format we asked for...
# category_match = re.search(r"Category:\s*(\w+)", reply)
# priority_match = re.search(r"Priority:\s*(\w+)", reply)
# category = category_match.group(1) if category_match else None
# priority = priority_match.group(1) if priority_match else None
# return category, priority