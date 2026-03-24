import logging
from typing import List, Tuple, Dict, Any
from manual_to_uml.core.ibr_schema import IBR, State, Transition, Variable, VariableType
from manual_to_uml.extraction.preprocessor import Sentence
from manual_to_uml.extraction.procedural_event_parser import parse_event
from manual_to_uml.extraction.procedural_guard_parser import parse_guard
from manual_to_uml.extraction.guard_parser import GuardParser

logger = logging.getLogger(__name__)

def build_procedural_fsm(sentences: List[Sentence]) -> Tuple[IBR, List[str]]:
    """
    Constructs an FSM sequentially from ordered sentences safely bypassing the complex
    state abstractor heuristics and LLM inference generation rules completely.
    """
    states_dict: Dict[str, State] = {}
    transitions: List[Transition] = []
    variables_dict: Dict[str, Variable] = {}
    source_map: Dict[str, str] = {s.id: s.text for s in sentences}
    human_review_flags: List[str] = []

    logger.info(f"[ProceduralBuilder] Creating deterministic FSM from {len(sentences)} steps...")

    # Force initial
    first_id = sentences[0].id if sentences else "s0"
    states_dict["Initial"] = State(id="Initial", name="Initial", is_initial=True, source_sentence_ids=[first_id])
    prev_state = "Initial"
    t_counter = 1

    for i, s in enumerate(sentences):
        text_lower = s.text.lower()
        
        # Base event heuristic
        raw_event = parse_event(s)
        
        # Is it conditional branching?
        is_conditional = "if " in text_lower
        guard_data = None
        guard_node = None
        
        if is_conditional:
            guard_data = parse_guard(text_lower)
            if guard_data:
                # Add to var registry matching schema types
                v_name = guard_data["variable"]
                v_val = guard_data["value"]
                if v_name not in variables_dict:
                    v_type = VariableType.FLOAT
                    if isinstance(v_val, bool):
                        v_type = VariableType.BOOLEAN
                    elif isinstance(v_val, int) and not isinstance(v_val, bool):
                        v_type = VariableType.INT
                    variables_dict[v_name] = Variable(name=v_name, type=v_type)
                
                # Format into schema-compliant GuardNode natively
                guard_node = {
                    "node_type": "condition",
                    "variable": v_name,
                    "operator": guard_data["operator"],
                    "literal_value": guard_data["value"],
                    "left": None,
                    "right": None
                }
            else:
                human_review_flags.append(f"Conditional sentence '{s.id}' bypassed deterministic regex guard matching.")

        # Naming state logic
        # Either standard "Step X" wrapper or we can use the main verb
        verb = raw_event.split("_")[0].capitalize()
        state_name = f"Step_{i+1}"
        if raw_event != "unknown_event":
             state_name = verb

        # Avoid duplicates deterministically
        while state_name in states_dict:
             state_name += "_"

        # Create sequential state
        b_fault = any(f in state_name.lower() or f in text_lower for f in ["emergency", "leak", "temperature", "pressure", "fault"])
        states_dict[state_name] = State(
            id=state_name,
            name=state_name.replace("_", " "),
            is_fault=b_fault,
            source_sentence_ids=[s.id],
            entry_action=s.text
        )

        display_l = raw_event.replace("_", " ") if raw_event != "unknown_event" else f"goto_{state_name.lower()}"

        # If it's a conditional, the system should technically branch OUT of the PREVIOUS state into this one conditionally
        # And standardly fall-through to the NEXT state. For procedural purity, we just link 'prev_state -> state_name' 
        # using the guard constraint, acting as an isolated physical check.
        t = Transition(
            id=f"t{t_counter:03d}",
            from_state=prev_state,
            to_state=state_name,
            event=raw_event if raw_event != "unknown_event" else f"goto_{state_name.lower()}",
            display_label=display_l,
            guard=guard_node,
            source_sentence_ids=[s.id]
        )
        transitions.append(t)
        t_counter += 1
        
        # Do not advance prev_state if this was a conditional branch acting outside the main sequential flow
        if not is_conditional:
             prev_state = state_name

    # End
    all_sids = [s.id for s in sentences]
    states_dict["Terminal"] = State(id="Terminal", name="Terminal", is_terminal=True, source_sentence_ids=all_sids)
    transitions.append(Transition(
        id=f"t{t_counter:03d}",
        from_state=prev_state,
        to_state="Terminal",
        event="complete",
        display_label="complete",
        source_sentence_ids=[sentences[-1].id] if sentences else []
    ))

    ibr = IBR(
        version="1.0",
        manual_id="deterministic_procedural",
        states=list(states_dict.values()),
        transitions=transitions,
        variables=variables_dict,
        source_sentences=source_map
    )
    
    return ibr, human_review_flags
