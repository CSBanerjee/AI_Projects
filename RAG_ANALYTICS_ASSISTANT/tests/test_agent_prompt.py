from app.hitl import agent_prompt

def test_prompt_contains_original_question():
    msg = agent_prompt.build_escalation_message("What is ASP?")
    assert "What is ASP?" in msg

def test_prompt_contains_yes_and_no():
    msg = agent_prompt.build_escalation_message("test")
    assert "Yes" in msg
    assert "No" in msg

def test_prompt_is_non_empty_string():
    msg = agent_prompt.build_escalation_message("test")
    assert isinstance(msg, str)
    assert len(msg.strip()) > 0