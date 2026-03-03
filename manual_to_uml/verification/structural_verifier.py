import networkx as nx
from typing import List
from pydantic import BaseModel
from manual_to_uml.core.ibr_schema import IBR

class StructuralIssue(BaseModel):
    issue_type: str
    severity: str  # ERROR / WARNING / INFO
    affected_states: List[str]
    affected_transitions: List[str]
    description: str
    source_sentence_ids: List[str]

def build_graph(ibr: IBR) -> nx.DiGraph:
    G = nx.DiGraph()
    for state in ibr.states:
        G.add_node(
            state.id, 
            name=state.name,
            is_initial=state.is_initial,
            is_terminal=state.is_terminal
        )
    for t in ibr.transitions:
        G.add_edge(
            t.from_state, 
            t.to_state, 
            id=t.id,
            event=t.event,
            has_guard=t.guard is not None,
            action=t.action
        )
    return G

def check_initial_state(graph: nx.DiGraph, ibr: IBR) -> List[StructuralIssue]:
    issues = []
    initial_states = [n for n, attr in graph.nodes(data=True) if attr.get('is_initial', False)]
    if len(initial_states) == 0:
        issues.append(StructuralIssue(
            issue_type="MISSING_INITIAL_STATE",
            severity="ERROR",
            affected_states=[],
            affected_transitions=[],
            description="The model must have exactly one initial state, but none were found.",
            source_sentence_ids=[]
        ))
    elif len(initial_states) > 1:
        issues.append(StructuralIssue(
            issue_type="MULTIPLE_INITIAL_STATES",
            severity="ERROR",
            affected_states=initial_states,
            affected_transitions=[],
            description=f"The model must have exactly one initial state. Found {len(initial_states)}.",
            source_sentence_ids=[]
        ))
    return issues

def check_unreachable_states(graph: nx.DiGraph, ibr: IBR) -> List[StructuralIssue]:
    issues = []
    initial_states = [n for n, attr in graph.nodes(data=True) if attr.get('is_initial', False)]
    if not initial_states:
        return issues
        
    start_node = initial_states[0]
    reachable = set()
    if start_node in graph:
        reachable = set(nx.descendants(graph, start_node))
        reachable.add(start_node)
        
    unreachable = set(graph.nodes()) - reachable
    if unreachable:
        issues.append(StructuralIssue(
            issue_type="UNREACHABLE_STATE",
            severity="WARNING",
            affected_states=list(unreachable),
            affected_transitions=[],
            description="The model contains states that cannot be reached from the initial state.",
            source_sentence_ids=[]
        ))
    return issues

def check_dead_end_states(graph: nx.DiGraph, ibr: IBR) -> List[StructuralIssue]:
    issues = []
    for node, attr in graph.nodes(data=True):
        if not attr.get('is_terminal', False) and graph.out_degree(node) == 0:
            issues.append(StructuralIssue(
                issue_type="DEAD_END_STATE",
                severity="ERROR",
                affected_states=[node],
                affected_transitions=[],
                description=f"State '{node}' is not marked as terminal but has no outgoing transitions.",
                source_sentence_ids=[]
            ))
    return issues

def check_missing_guards(ibr: IBR) -> List[StructuralIssue]:
    issues = []
    grouped = {}
    for t in ibr.transitions:
        key = (t.from_state, t.event)
        if key not in grouped: grouped[key] = []
        grouped[key].append(t)
        
    for key, transitions in grouped.items():
        if len(transitions) > 1:
            missing = [t for t in transitions if not t.guard]
            if missing:
                issues.append(StructuralIssue(
                    issue_type="MISSING_GUARD_ON_BRANCH",
                    severity="ERROR",
                    affected_states=[key[0]],
                    affected_transitions=[t.id for t in missing],
                    description=f"Branching transition on event '{key[1]}' from state '{key[0]}' is missing guards.",
                    source_sentence_ids=[sid for t in missing for sid in t.source_sentence_ids]
                ))
    return issues

def check_duplicate_transitions(ibr: IBR) -> List[StructuralIssue]:
    issues = []
    seen = set()
    for t in ibr.transitions:
        guard_str = str(t.guard.model_dump()) if t.guard else "None"
        sig = (t.from_state, t.to_state, t.event, guard_str)
        if sig in seen:
            issues.append(StructuralIssue(
                issue_type="DUPLICATE_TRANSITION",
                severity="ERROR",
                affected_states=[t.from_state, t.to_state],
                affected_transitions=[t.id],
                description=f"Transition {t.id} is a duplicate of a previously declared transition.",
                source_sentence_ids=t.source_sentence_ids
            ))
        else:
            seen.add(sig)
    return issues

def verify_structure(ibr: IBR) -> List[StructuralIssue]:
    graph = build_graph(ibr)
    issues = []
    issues.extend(check_initial_state(graph, ibr))
    issues.extend(check_unreachable_states(graph, ibr))
    issues.extend(check_dead_end_states(graph, ibr))
    issues.extend(check_missing_guards(ibr))
    issues.extend(check_duplicate_transitions(ibr))
    return issues
