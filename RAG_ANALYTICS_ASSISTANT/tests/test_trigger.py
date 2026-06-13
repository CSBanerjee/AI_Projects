from app.hitl import trigger

def test_low_confidence_returns_true():
    assert trigger.should_escalate(0.5) is True

def test_high_confidence_returns_false():
    assert trigger.should_escalate(0.85) is False

def test_exactly_at_threshold_returns_false():
    # 0.7 is not below 0.7
    assert trigger.should_escalate(0.7) is False

def test_zero_confidence_returns_true():
    assert trigger.should_escalate(0.0) is True