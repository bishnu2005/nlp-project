import pytest
import os
from manual_to_uml.core.ibr_schema import IBR
from manual_to_uml.verification.structural_verifier import StructuralIssue
from manual_to_uml.verification.z3_verifier import GuardConflict, ConflictType
from manual_to_uml.generation.report_generator import build_report, render_report_html, ConformanceReport

@pytest.fixture
def empty_ibr():
    return IBR(
        version="1.0",
        manual_id="m1",
        states=[],
        transitions=[],
        variables={},
        source_sentences={}
    )

def test_report_summary_counts(empty_ibr):
    struct_issues = [
        StructuralIssue(issue_type="DEAD_END_STATE", severity="ERROR", affected_states=["s1"], affected_transitions=[], description="test", source_sentence_ids=[]),
        StructuralIssue(issue_type="UNREACHABLE_STATE", severity="WARNING", affected_states=["s2"], affected_transitions=[], description="test", source_sentence_ids=[])
    ]
    guard_issues = [
        GuardConflict(conflict_type=ConflictType.OVERLAP, severity="ERROR", transition_ids=["t1", "t2"], description="test", source_sentence_ids=[])
    ]
    
    report = build_report(empty_ibr, struct_issues, guard_issues, [])
    assert report.summary["ERROR"] == 2
    assert report.summary["WARNING"] == 1
    assert report.summary["INFO"] == 0

def test_report_item_sorting(empty_ibr):
    struct_issues = [
        StructuralIssue(issue_type="UNREACHABLE_STATE", severity="WARNING", affected_states=["s2"], affected_transitions=[], description="test", source_sentence_ids=[])
    ]
    guard_issues = [
        GuardConflict(conflict_type=ConflictType.OVERLAP, severity="ERROR", transition_ids=["t1"], description="test", source_sentence_ids=[])
    ]
    ambiguities = [
        {"ambiguity_type": "VAGUE_QUANTIFIER", "sentence_id": "s1", "sentence_text": "text", "resolution": "r", "confidence": 0.8}
    ]
    
    report = build_report(empty_ibr, struct_issues, guard_issues, ambiguities)
    #ERROR should be first
    assert report.items[0].severity == "ERROR"
    assert report.items[1].severity == "WARNING"
    assert report.items[2].severity == "WARNING"

def test_empty_issues_clean_report(empty_ibr):
    report = build_report(empty_ibr, [], [], [])
    assert report.summary["ERROR"] == 0
    assert report.summary["WARNING"] == 0
    assert report.summary["INFO"] == 0
    assert len(report.items) == 0

def test_html_rendering(tmp_path, empty_ibr):
    struct_issues = [
        StructuralIssue(issue_type="DEAD_END_STATE", severity="ERROR", affected_states=["s1"], affected_transitions=[], description="desc1", source_sentence_ids=["sent1"])
    ]
    report = build_report(empty_ibr, struct_issues, [], [])
    out_path = str(tmp_path / "test_report.html")
    
    result = render_report_html(report, out_path)
    assert result is True
    
    with open(out_path, "r", encoding="utf-8") as f:
        html = f.read()
        assert "DEAD_END_STATE" in html
        assert "desc1" in html
        assert "severity-ERROR" in html
        assert "sent1" in html
