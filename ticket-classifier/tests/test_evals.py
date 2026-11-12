from ticket_classifier.evals import called, code_printed_count, count_calls, observed

TRACE = [
    "[T-1] step 1 Action: web_fetch({'url': 'https://status.mollie.com/x'})",
    "[T-1] step 2 Action: bash_code_execution({'command': 'grep'})",
    "[T-1] step 2 Observation: code execution exit 0: line one\ncount=5\n",
    "[T-1] step 3 Observation: No duplicate charges found for client 1003",
]


def test_called_matches_tool_and_argument():
    assert called(TRACE, "web_fetch", "status.mollie")
    assert not called(TRACE, "web_fetch", "payments.json")
    assert not called(TRACE, "find_duplicate_charges")


def test_count_calls():
    assert count_calls(TRACE, "bash_code_execution") == 1


def test_observed_ignores_actions():
    assert observed(TRACE, "No duplicate charges")
    assert not observed(TRACE, "grep")  # only appears in an Action


def test_code_printed_count_needs_the_number_on_its_own_line():
    assert code_printed_count(TRACE, 5)
    assert not code_printed_count(TRACE, 8)
    assert not code_printed_count(["Observation: code execution exit 0: 15:02"], 5)


def test_code_printed_count_accepts_a_single_line_result():
    assert code_printed_count(["Observation: code execution exit 0: 5"], 5)
