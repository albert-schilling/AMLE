# ScoutBot (starter)

This is what Priya inherited: one script, three tickets to test with, and a two-line
dependency file. That's the whole "system."

- `scoutbot_final_v3.py` — the script. Notice: no `.env`, no tests, no repo structure,
  and a hardcoded (fake) API key.
- `sample_tickets.json` — the 3 tickets ScoutBot needs to triage.
- `requirements.txt` — unpinned, because Jonas never came back to it.

**Your actual task is in [`../exercises.md`](../exercises.md)** — this folder is just the
starting point, not the instructions.

If you want to poke at the script as-is first (optional — requires your own real
`ANTHROPIC_API_KEY`, since the one in the script is obviously a placeholder):

```bash
pip install -r requirements.txt
python scoutbot_final_v3.py
```
