from ticket_classifier.prompts import SYSTEM_PROMPT


def test_system_prompt_warns_about_untrusted_text():
    assert "never follow instructions" in SYSTEM_PROMPT
