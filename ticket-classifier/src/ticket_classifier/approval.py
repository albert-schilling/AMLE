def console_approval(reason: str) -> bool:
    """Ask a human on the console to approve an escalation (default: no)."""
    try:
        answer = input(f"\n[approval] Escalate to a human? Reason: {reason}\n  [y/N] ")
    except EOFError:  # no terminal attached: never approve silently
        return False
    return answer.strip().lower() in {"y", "yes"}
