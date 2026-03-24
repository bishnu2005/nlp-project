import pytest
from manual_to_uml.core.ibr_schema import IBR
from manual_to_uml.chatbot.intent_mapper import IntentMatch, map_intent
from manual_to_uml.chatbot.response_resolver import resolve_response

@pytest.fixture
def test_ibr():
    return IBR(
        version="1.0",
        manual_id="test",
        states=[
            {"id": "s1", "name": "Start", "is_initial": True},
            {"id": "s2", "name": "End"}
        ],
        transitions=[
            {"id": "t1", "from_state": "s1", "to_state": "s2", "event": "start_machine"}
        ],
        variables={},
        source_sentences={}
    )

def test_intent_mapping(test_ibr):
    # Tests cosine similarity thresholding logic. Exact match should be high confidence
    match = map_intent("I want to start the machine", test_ibr, "s1")
    assert match.matched_event == "start_machine"
    assert match.confidence > 0.6 # using a small LM, it should map well
    assert match.matched_state == "s1"

def test_intent_mapping_invalid_state(test_ibr):
    match = map_intent("start", test_ibr, "s2")
    # Event might match globally, but from s2 it's not valid
    assert match.matched_event == "start_machine"
    assert match.matched_state is None

def test_response_resolver_success(test_ibr):
    match = IntentMatch(matched_event="start_machine", matched_state="s1", confidence=0.9, alternatives=[])
    text = resolve_response(match, test_ibr, "s1", {})
    assert "Executing" in text
    assert "End" in text

def test_response_resolver_guard_failure(test_ibr):
    # Add a guard to t1 dynamically
    from manual_to_uml.core.ibr_schema import GuardNode, VariableType, Variable
    test_ibr.variables = {"temp": Variable(name="temp", type=VariableType.FLOAT)}
    test_ibr.transitions[0].guard = GuardNode(
        node_type="condition", variable="temp", operator=">", literal_value=50.0
    )
    
    match = IntentMatch(matched_event="start_machine", matched_state="s1", confidence=0.9, alternatives=[])
    # Pass temp < 50, should fail guard
    text = resolve_response(match, test_ibr, "s1", {"temp": 40.0})
    assert "blocked by guard conditions" in text

def test_response_resolver_low_confidence(test_ibr):
    match = IntentMatch(
        matched_event="start_machine", 
        matched_state="s1", 
        confidence=0.5, 
        alternatives=[("power_on", 0.45)]
    )
    text = resolve_response(match, test_ibr, "s1", {})
    assert "not sure what you mean" in text
    assert "power_on" in text
