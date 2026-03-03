import pytest
from manual_to_uml.core.ibr_schema import IBR, State, Transition, GuardNode, GuardNodeType, Variable, VariableType
from manual_to_uml.generation.diff_engine import diff_ibr, DiffItem

@pytest.fixture
def base_ibr():
    return IBR(
        version="1.0",
        manual_id="m1",
        states=[State(id="s1", name="S1", is_initial=True)],
        transitions=[Transition(id="t1", from_state="s1", to_state="s2", event="start", 
                                guard=GuardNode(node_type=GuardNodeType.CONDITION, variable="v", operator=">", literal_value=5))],
        variables={"v": Variable(name="v", type=VariableType.INT)},
        source_sentences={}
    )

def clone_ibr(ibr: IBR) -> IBR:
    return IBR.model_validate(ibr.model_dump())

def test_identical_ibrs(base_ibr):
    v2 = clone_ibr(base_ibr)
    diffs = diff_ibr(base_ibr, v2)
    assert len(diffs) == 0

def test_added_state(base_ibr):
    v2 = clone_ibr(base_ibr)
    v2.states.append(State(id="s2", name="S2"))
    diffs = diff_ibr(base_ibr, v2)
    
    assert len(diffs) == 1
    assert diffs[0].change_type == "ADDED"
    assert diffs[0].element_type == "STATE"
    assert diffs[0].element_id == "s2"

def test_removed_transition(base_ibr):
    v2 = clone_ibr(base_ibr)
    v2.transitions = []
    diffs = diff_ibr(base_ibr, v2)
    
    assert len(diffs) == 1
    assert diffs[0].change_type == "REMOVED"
    assert diffs[0].element_type == "TRANSITION"
    assert diffs[0].element_id == "t1"

def test_modified_guard(base_ibr):
    v2 = clone_ibr(base_ibr)
    # Changing threshold from 5 to 10
    v2.transitions[0].guard.literal_value = 10
    diffs = diff_ibr(base_ibr, v2)
    
    # finding guard modification
    guard_diff = [d for d in diffs if d.element_type == "GUARD"]
    assert len(guard_diff) == 1
    assert guard_diff[0].change_type == "MODIFIED"
    assert guard_diff[0].old_value["literal_value"] == 5
    assert guard_diff[0].new_value["literal_value"] == 10

def test_modified_variable_type(base_ibr):
    v2 = clone_ibr(base_ibr)
    v2.variables["v"].type = VariableType.FLOAT
    diffs = diff_ibr(base_ibr, v2)
    
    var_diff = [d for d in diffs if d.element_type == "VARIABLE"]
    assert len(var_diff) == 1
    assert var_diff[0].change_type == "MODIFIED"
    assert var_diff[0].old_value["type"] == "int"
    assert var_diff[0].new_value["type"] == "float"
