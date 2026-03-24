import pytest
from pydantic import ValidationError
from manual_to_uml.core.ibr_schema import (
    VariableType, Variable, GuardNodeType, GuardNode,
    Transition, State, IBR
)

def test_valid_ibr():
    ibr = IBR(
        version="1.0",
        manual_id="m1",
        states=[
            State(id="s1", name="Init", is_initial=True),
            State(id="s2", name="Running"),
            State(id="s3", name="End", is_terminal=True)
        ],
        transitions=[
            Transition(id="t1", from_state="s1", to_state="s2", event="start"),
            Transition(id="t2", from_state="s2", to_state="s3", event="stop")
        ],
        variables={},
        source_sentences={"s001": "Dummy"}
    )
    assert len(ibr.states) == 3
    assert len(ibr.transitions) == 2

def test_no_initial_state_raises_error():
    with pytest.raises(ValidationError) as exc_info:
        IBR(
            version="1.0",
            manual_id="m1",
            states=[
                State(id="s1", name="Running")
            ],
            transitions=[],
            variables={},
            source_sentences={}
        )
    assert "at least one initial state" in str(exc_info.value)

def test_duplicate_state_ids_raises_error():
    with pytest.raises(ValidationError) as exc_info:
        IBR(
            version="1.0",
            manual_id="m1",
            states=[
                State(id="s1", name="Init", is_initial=True),
                State(id="s1", name="Duplicate")
            ],
            transitions=[],
            variables={},
            source_sentences={}
        )
    assert "State IDs must be unique" in str(exc_info.value)

def test_mismatched_variable_type_raises_error():
    guard = GuardNode(
        node_type=GuardNodeType.CONDITION,
        variable="temp",
        operator=">",
        literal_value="high"  # Should be float/int
    )
    with pytest.raises(ValidationError) as exc_info:
        IBR(
            version="1.0",
            manual_id="m1",
            states=[State(id="s1", name="Init", is_initial=True)],
            transitions=[
                Transition(id="t1", from_state="s1", to_state="s1", event="check", guard=guard)
            ],
            variables={
                "temp": Variable(name="temp", type=VariableType.FLOAT)
            },
            source_sentences={}
        )
    assert "Type mismatch" in str(exc_info.value)

def test_empty_states_raises_error():
    with pytest.raises(ValidationError) as exc_info:
        IBR(version="1.0", manual_id="m1", states=[], transitions=[], variables={}, source_sentences={})
    assert "at least one state" in str(exc_info.value)
