import os
import datetime
from typing import List, Dict
from pydantic import BaseModel
from jinja2 import Environment, FileSystemLoader

from manual_to_uml.core.ibr_schema import IBR
from manual_to_uml.verification.structural_verifier import StructuralIssue
from manual_to_uml.verification.z3_verifier import GuardConflict

class ReportItem(BaseModel):
    item_id: str        # E01, W01, I01 etc.
    severity: str       # ERROR / WARNING / INFO
    category: str       # STRUCTURAL / GUARD / AMBIGUITY
    title: str
    description: str
    affected_elements: List[str]
    source_sentences: List[str]
    recommendation: str

class ConformanceReport(BaseModel):
    manual_id: str
    generated_at: str
    summary: Dict[str, int]  # {ERROR: 3, WARNING: 7, INFO: 2}
    items: List[ReportItem]

def format_elements(states: List[str], transitions: List[str]) -> List[str]:
    elements = []
    if states:
        elements.extend([f"State: {s}" for s in states])
    if transitions:
        elements.extend([f"Transition: {t}" for t in transitions])
    return elements

def build_report(ibr: IBR, 
                 structural_issues: List[StructuralIssue],
                 guard_conflicts: List[GuardConflict],
                 ambiguities: List[dict]) -> ConformanceReport:
    items = []
    
    error_count = 0
    warning_count = 0
    info_count = 0
    
    def process_issue(severity: str, category: str, title: str, desc: str, elements: List[str], sentences: List[str], rec: str):
        nonlocal error_count, warning_count, info_count
        if severity == "ERROR":
            error_count += 1
            item_id = f"E{error_count:02d}"
        elif severity == "WARNING":
            warning_count += 1
            item_id = f"W{warning_count:02d}"
        else:
            info_count += 1
            item_id = f"I{info_count:02d}"
            
        items.append(ReportItem(
            item_id=item_id,
            severity=severity,
            category=category,
            title=title,
            description=desc,
            affected_elements=elements,
            source_sentences=sentences,
            recommendation=rec
        ))

    for issue in structural_issues:
        rec = "Review diagram structure."
        if issue.issue_type == "MISSING_INITIAL_STATE":
            rec = "Add an initial state to the model."
        elif issue.issue_type == "DEAD_END_STATE":
            rec = "Ensure state has outgoing transitions or mark as terminal."
        elif issue.issue_type == "UNREACHABLE_STATE":
            rec = "Verify transitions leading to this state."
            
        process_issue(
            severity=issue.severity,
            category="STRUCTURAL",
            title=issue.issue_type,
            desc=issue.description,
            elements=format_elements(issue.affected_states, issue.affected_transitions),
            sentences=issue.source_sentence_ids,
            rec=rec
        )
        
    for conflict in guard_conflicts:
        rec = "Review guard logic."
        if conflict.conflict_type.value == "OVERLAP":
            rec = "Ensure guards on branching transitions are mutually exclusive."
        elif conflict.conflict_type.value == "MISSING_ELSE":
            rec = "Ensure guards cover all possible input domains (add else/fallback branch)."
        elif conflict.conflict_type.value == "UNSATISFIABLE":
            rec = "Fix guard expression to allow it to evaluate to true."
            
        process_issue(
            severity=conflict.severity,
            category="GUARD",
            title=conflict.conflict_type.value,
            desc=conflict.description,
            elements=format_elements([], conflict.transition_ids),
            sentences=conflict.source_sentence_ids,
            rec=rec
        )
        
    for ambig in ambiguities:
        process_issue(
            severity="WARNING", # Treating ambiguities as warnings for now
            category="AMBIGUITY",
            title=ambig.get("ambiguity_type", "AMBIGUITY"),
            desc=ambig.get("sentence_text", ""),
            elements=[],
            sentences=[ambig.get("sentence_id", "")],
            rec=ambig.get("resolution", "REQUIRES_HUMAN_CLARIFICATION")
        )

    # Sort priorities: ERROR > WARNING > INFO
    severity_order = {"ERROR": 0, "WARNING": 1, "INFO": 2}
    items.sort(key=lambda x: severity_order.get(x.severity, 3))

    return ConformanceReport(
        manual_id=ibr.manual_id,
        generated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        summary={
            "ERROR": error_count,
            "WARNING": warning_count,
            "INFO": info_count
        },
        items=items
    )

def render_report_html(report: ConformanceReport, output_path: str) -> bool:
    try:
        # Load template
        # Assume templates folder is at root of project and we are running from root or one level down
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        templates_dir = os.path.join(project_root, "templates")
        
        # Fallback for testing if run differently
        if not os.path.exists(templates_dir):
            templates_dir = os.path.join(os.getcwd(), "templates")
            
        env = FileSystemLoader(os.path.abspath(templates_dir))
        jinja_env = Environment(loader=env)
        template = jinja_env.get_template("conformance_report.html")
        
        html_content = template.render(report=report.model_dump())
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
            
        return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False
