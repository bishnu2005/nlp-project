import pytest
from manual_to_uml.core.ibr_schema import IBR, State, Transition, Variable, VariableType
from manual_to_uml.core.guard_dsl import parse_guard
from manual_to_uml.verification.z3_verifier import verify_ibr, ConflictType

@pytest.fixture
def base_registry():
    return {
        "temp": Variable(name="temp", type=VariableType.FLOAT)
    }

def build_ibr(transitions, base_registry):
    return IBR(
        version="1.0",
        manual_id="m1",
        states=[
            State(id="s1", name="S1", is_initial=True),
            State(id="s2", name="S2"),
            State(id="s3", name="S3")
        ],
        transitions=transitions,
        variables=base_registry,
        source_sentences={}
    )

def test_overlap(base_registry):
    t1 = Transition(id="t1", from_state="s1", to_state="s2", event="ev", guard=parse_guard("temp > 40", base_registry))
    t2 = Transition(id="t2", from_state="s1", to_state="s3", event="ev", guard=parse_guard("temp > 50", base_registry))
    
    ibr = build_ibr([t1, t2], base_registry)
    conflicts = verify_ibr(ibr)
    
    overlaps = [c for c in conflicts if c.conflict_type == ConflictType.OVERLAP]
    assert len(overlaps) == 1
    assert set(overlaps[0].transition_ids) == {"t1", "t2"}

def test_unsatisfiable(base_registry):
    t1 = Transition(id="t1", from_state="s1", to_state="s2", event="ev", guard=parse_guard("temp > 50 AND temp < 40", base_registry))
    ibr = build_ibr([t1], base_registry)
    conflicts = verify_ibr(ibr)
    
    unsat = [c for c in conflicts if c.conflict_type == ConflictType.UNSATISFIABLE]
    assert len(unsat) == 1

def test_always_true(base_registry):
    t1 = Transition(id="t1", from_state="s1", to_state="s2", event="ev", guard=parse_guard("temp > 0 OR temp <= 0", base_registry))
    ibr = build_ibr([t1], base_registry)
    conflicts = verify_ibr(ibr)
    
    always = [c for c in conflicts if c.conflict_type == ConflictType.ALWAYS_TRUE]
    assert len(always) == 1

def test_no_overlap_full_coverage(base_registry):
    t1 = Transition(id="t1", from_state="s1", to_state="s2", event="ev", guard=parse_guard("temp > 50", base_registry))
    t2 = Transition(id="t2", from_state="s1", to_state="s3", event="ev", guard=parse_guard("temp <= 50", base_registry))
    ibr = build_ibr([t1, t2], base_registry)
    conflicts = verify_ibr(ibr)
    
    assert len(conflicts) == 0

def test_missing_else(base_registry):
    t1 = Transition(id="t1", from_state="s1", to_state="s2", event="ev", guard=parse_guard("temp > 50", base_registry))
    t2 = Transition(id="t2", from_state="s1", to_state="s3", event="ev", guard=parse_guard("temp < 30", base_registry))
    ibr = build_ibr([t1, t2], base_registry)
    conflicts = verify_ibr(ibr)
    
    missing = [c for c in conflicts if c.conflict_type == ConflictType.MISSING_ELSE]
    assert len(missing) == 1
