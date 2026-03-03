import pytest
from manual_to_uml.core.ibr_schema import IBR, State, Transition, GuardNode, GuardNodeType
from manual_to_uml.verification.structural_verifier import verify_structure

def force_ibr(**kwargs):
    return IBR.model_construct(**kwargs)

def test_missing_initial_state():
    ibr = force_ibr(
        version="1.0", manual_id="m1", variables={}, source_sentences={},
        states=[State(id="s1", name="S1", source_sentence_ids=[])],
        transitions=[]
    )
    issues = verify_structure(ibr)
    assert any(i.issue_type == "MISSING_INITIAL_STATE" for i in issues)

def test_unreachable_state():
    ibr = force_ibr(
        version="1.0", manual_id="m1", variables={}, source_sentences={},
        states=[
            State(id="s1", name="S1", is_initial=True, source_sentence_ids=[]),
            State(id="s2", name="orphan", is_terminal=True, source_sentence_ids=[])
        ],
        transitions=[]
    )
    issues = verify_structure(ibr)
    unreachable = [i for i in issues if i.issue_type == "UNREACHABLE_STATE"]
    assert len(unreachable) == 1
    assert "s2" in unreachable[0].affected_states

def test_dead_end_state():
    ibr = force_ibr(
        version="1.0", manual_id="m1", variables={}, source_sentences={},
        states=[
            State(id="s1", name="S1", is_initial=True, source_sentence_ids=[]),
            State(id="s2", name="S2", source_sentence_ids=[])
        ],
        transitions=[
            Transition(id="t1", from_state="s1", to_state="s2", event="ev", source_sentence_ids=[])
        ]
    )
    issues = verify_structure(ibr)
    dead_ends = [i for i in issues if i.issue_type == "DEAD_END_STATE"]
    assert len(dead_ends) == 1
    assert "s2" in dead_ends[0].affected_states

def test_missing_guards_branching():
    ibr = force_ibr(
        version="1.0", manual_id="m1", variables={}, source_sentences={},
        states=[
            State(id="s1", name="S1", is_initial=True, source_sentence_ids=[]),
            State(id="s2", name="S2", is_terminal=True, source_sentence_ids=[]),
            State(id="s3", name="S3", is_terminal=True, source_sentence_ids=[])
        ],
        transitions=[
            Transition(id="t1", from_state="s1", to_state="s2", event="ev", source_sentence_ids=[]),
            Transition(id="t2", from_state="s1", to_state="s3", event="ev", guard=GuardNode(node_type=GuardNodeType.CONDITION, variable="v", operator=">", literal_value=1), source_sentence_ids=[])
        ]
    )
    issues = verify_structure(ibr)
    missing = [i for i in issues if i.issue_type == "MISSING_GUARD_ON_BRANCH"]
    assert len(missing) == 1
    assert "t1" in missing[0].affected_transitions

def test_valid_ibr():
    ibr = force_ibr(
        version="1.0", manual_id="m1", variables={}, source_sentences={},
        states=[
            State(id="s1", name="S1", is_initial=True, source_sentence_ids=[]),
            State(id="s2", name="S2", is_terminal=True, source_sentence_ids=[])
        ],
        transitions=[
            Transition(id="t1", from_state="s1", to_state="s2", event="ev", source_sentence_ids=[])
        ]
    )
    assert len(verify_structure(ibr)) == 0

def test_duplicate_transitions():
    ibr = force_ibr(
        version="1.0", manual_id="m1", variables={}, source_sentences={},
        states=[
            State(id="s1", name="S1", is_initial=True, source_sentence_ids=[]),
            State(id="s2", name="S2", is_terminal=True, source_sentence_ids=[])
        ],
        transitions=[
            Transition(id="t1", from_state="s1", to_state="s2", event="ev", source_sentence_ids=[]),
            Transition(id="t2", from_state="s1", to_state="s2", event="ev", source_sentence_ids=[])
        ]
    )
    issues = verify_structure(ibr)
    dups = [i for i in issues if i.issue_type == "DUPLICATE_TRANSITION"]
    assert len(dups) == 1
    assert "t2" in dups[0].affected_transitions
