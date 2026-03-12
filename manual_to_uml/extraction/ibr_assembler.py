import logging
from typing import List, Dict, Tuple
from manual_to_uml.core.ibr_schema import IBR, State, Transition, Variable, VariableType
from manual_to_uml.extraction.guard_parser import GuardParser
from manual_to_uml.extraction.llm_extractor import ExtractionResult
from manual_to_uml.extraction.preprocessor import Sentence
from manual_to_uml.extraction.symbolic_normalizer import SymbolicNormalizer

logger = logging.getLogger(__name__)

class IBRAssembler:
    def __init__(self):
        self.normalizer = SymbolicNormalizer()

    def assemble(self, extractions: List[ExtractionResult], original_sentences: List[Sentence]) -> Tuple[IBR, List[str]]:
        states_dict: Dict[str, State] = {}
        transitions: List[Transition] = []
        variables_dict: Dict[str, Variable] = {}
        source_map: Dict[str, str] = {s.id: s.text for s in original_sentences}
        human_review_flags: List[str] = []

        # 1. First pass: Collect states and infer variables
        for res in extractions:
            if res.confidence < 0.75:
                human_review_flags.append(f"Low confidence ({res.confidence}) extraction for sentence {res.sentence_id}")

            # Register Variables
            for var in res.variables_mentioned:
                v_name = var.replace(" ", "_")
                if v_name not in variables_dict:
                    v_type = self.normalizer.infer_type(v_name)
                    # For enum, we don't know the values yet until we parse guards maybe
                    variables_dict[v_name] = Variable(name=v_name, type=v_type)

            # Register States
            for state_name in res.states_mentioned:
                if state_name not in states_dict:
                    s_ids = res.source_sentence_ids if hasattr(res, "source_sentence_ids") and res.source_sentence_ids else [res.sentence_id]
                    st_lower = state_name.lower()
                    b_fault = any(f in st_lower for f in ["emergency", "leak", "temperature", "pressure", "vibration", "fault", "hazard"])
                    
                    states_dict[state_name] = State(
                        id=state_name, 
                        name=state_name.replace("_", " ").title(),
                        is_fault=b_fault,
                        source_sentence_ids=s_ids,
                        entry_action=res.entry_action
                    )
                else:
                    s_ids = res.source_sentence_ids if hasattr(res, "source_sentence_ids") and res.source_sentence_ids else [res.sentence_id]
                    for sid in s_ids:
                        if sid not in states_dict[state_name].source_sentence_ids:
                            states_dict[state_name].source_sentence_ids.append(sid)
                    # Merge entry actions if multiple blocks map to the same state
                    if res.entry_action and states_dict[state_name].entry_action and res.entry_action not in states_dict[state_name].entry_action:
                        states_dict[state_name].entry_action += "\n" + res.entry_action
                    elif res.entry_action and not states_dict[state_name].entry_action:
                        states_dict[state_name].entry_action = res.entry_action

        # 2. Second pass: Collect transitions and parse guards
        t_counter = 1
        for res in extractions:
            for t_data in res.transitions_implied:
                f_state = t_data.get("from")
                t_state = t_data.get("to")
                event = t_data.get("event", "unknown_event").replace(" ", "_")
                
                # Check for inconsistent state references
                s_ids = res.source_sentence_ids if hasattr(res, "source_sentence_ids") and res.source_sentence_ids else [res.sentence_id]
                if f_state not in states_dict:
                    b_fault_f = any(f in f_state.lower() for f in ["emergency", "leak", "temperature", "pressure", "vibration", "fault", "hazard"])
                    states_dict[f_state] = State(id=f_state, name=f_state.title(), is_fault=b_fault_f, source_sentence_ids=s_ids)
                if t_state not in states_dict:
                    b_fault_t = any(f in t_state.lower() for f in ["emergency", "leak", "temperature", "pressure", "vibration", "fault", "hazard"])
                    states_dict[t_state] = State(id=t_state, name=t_state.title(), is_fault=b_fault_t, source_sentence_ids=s_ids)
                    
                # Find matching guard
                guard_node = None
                for g in res.guards_implied:
                    if g.get("transition_event") == event or g.get("transition_event") == t_data.get("event"):
                        cond_str = g.get("condition")
                        if cond_str:
                            try:
                                # Normalize C-style operators often returned by LLMs
                                cond_str = cond_str.replace("&&", " AND ").replace("||", " OR ")
                                
                                # Use exact Recursive Descent Parser AST mapping
                                parser = GuardParser()
                                parsed_ast = parser.parse(cond_str)
                                
                                # Strict translation validation
                                if parsed_ast:
                                    guard_node = parsed_ast
                                    
                                    # Very basic auto-registration of variables detected on the left side of comparisons
                                    # to prevent z3 eval crashes later
                                    def _register_vars(ast):
                                        if not ast: return
                                        if ast.get("node_type") in ("AND", "OR", "NOT"):
                                            _register_vars(ast.get("left"))
                                            _register_vars(ast.get("right"))
                                            _register_vars(ast.get("operand"))
                                        elif ast.get("node_type") == "condition":
                                            v_name = ast.get("variable")
                                            if v_name and v_name not in variables_dict and str(v_name).replace("_", "").isalnum():
                                                val = ast.get("literal_value")
                                                v_type = VariableType.FLOAT
                                                if isinstance(val, bool):
                                                    v_type = VariableType.BOOLEAN
                                                elif isinstance(val, int) and not isinstance(val, bool):
                                                    v_type = VariableType.INT
                                                elif isinstance(val, str):
                                                    v_type = VariableType.STRING
                                                variables_dict[v_name] = Variable(name=v_name, type=v_type)
                                                    
                                    _register_vars(guard_node)
                                    
                            except Exception as e:
                                logger.warning(f"Could not parse guard '{cond_str}': {e}")
                                human_review_flags.append(f"Failed to parse guard condition '{cond_str}' in sentence {res.sentence_id}")
                                
                display_l = event.replace("_", " ")
                words = display_l.split()
                if len(words) > 3:
                     display_l = " ".join(words[:2]) + "..."
                     
                t = Transition(
                    id=f"t{t_counter:03d}",
                    from_state=f_state,
                    to_state=t_state,
                    event=event,
                    display_label=display_l,
                    guard=guard_node,
                    source_sentence_ids=s_ids
                )
                transitions.append(t)
                t_counter += 1
                
        # 2b. Event Ordering enforcing sequential construction
        def get_min_sid(tr):
            if not tr.source_sentence_ids: return ""
            return sorted(tr.source_sentence_ids)[0]
        transitions.sort(key=get_min_sid)
        
        # 2c. Transition Explosion Protection (Max 8 outgoing edges per state)
        grouped_trans = {}
        for t in transitions:
            grouped_trans.setdefault(t.from_state, []).append(t)
            
        capped_transitions = []
        for st, trans_list in grouped_trans.items():
            if len(trans_list) > 8:
                logger.warning(f"State '{st}' exceeded 8 outgoing transitions. Truncating excess to prevent cyclic explosion.")
                capped_transitions.extend(trans_list[:8])
            else:
                capped_transitions.extend(trans_list)
        transitions = capped_transitions

        # 3. Mark Initial/Terminal heuristics
        # State with outgoing but no incoming is initial
        # State with incoming but no outgoing is terminal
        states_list = list(states_dict.values())
        if states_list:
            incoming = set(t.to_state for t in transitions)
            outgoing = set(t.from_state for t in transitions)
            
            has_initial = False
            for s in states_list:
                if s.id not in incoming and s.id in outgoing:
                    s.is_initial = True
                    has_initial = True
                if s.id in incoming and s.id not in outgoing:
                    s.is_terminal = True
            
            if not has_initial and states_list:
                states_list[0].is_initial = True # Fallback

        ibr = IBR(
            version="1.0",
            manual_id="auto_extracted",
            states=states_list,
            transitions=transitions,
            variables=variables_dict,
            source_sentences=source_map
        )
        
        # Check for synonymous states flag
        syn_flags = self.normalizer.find_synonymous_states(list(states_dict.keys()))
        human_review_flags.extend(syn_flags)

        from manual_to_uml.config import DEBUG_PIPELINE
        if DEBUG_PIPELINE:
            logger.info("[DEBUG] FSM transitions")
            for t in transitions:
                logger.info({
                    "from": t.from_state,
                    "to": t.to_state,
                    "event": t.event,
                    "guard": t.guard,
                    "source_sentence_ids": t.source_sentence_ids
                })
                
        return ibr, human_review_flags
