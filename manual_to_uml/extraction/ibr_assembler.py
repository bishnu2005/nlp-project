import logging
from typing import List, Dict, Tuple
from manual_to_uml.core.ibr_schema import IBR, State, Transition, Variable, VariableType
from manual_to_uml.core.guard_dsl import parse_guard
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
                    states_dict[state_name] = State(
                        id=state_name, 
                        name=state_name.replace("_", " ").title(),
                        source_sentence_ids=[res.sentence_id]
                    )
                else:
                    if res.sentence_id not in states_dict[state_name].source_sentence_ids:
                        states_dict[state_name].source_sentence_ids.append(res.sentence_id)

        # 2. Second pass: Collect transitions and parse guards
        t_counter = 1
        for res in extractions:
            for t_data in res.transitions_implied:
                f_state = t_data.get("from")
                t_state = t_data.get("to")
                event = t_data.get("event", "unknown_event").replace(" ", "_")
                
                # Check for inconsistent state references
                if f_state not in states_dict:
                    states_dict[f_state] = State(id=f_state, name=f_state.title(), source_sentence_ids=[res.sentence_id])
                if t_state not in states_dict:
                    states_dict[t_state] = State(id=t_state, name=t_state.title(), source_sentence_ids=[res.sentence_id])
                    
                # Find matching guard
                guard_node = None
                for g in res.guards_implied:
                    if g.get("transition_event") == event or g.get("transition_event") == t_data.get("event"):
                        cond_str = g.get("condition")
                        if cond_str:
                            try:
                                # Ensure all variables used in guard are registered
                                # We'll do a sloppy auto-register just in case
                                guard_node = parse_guard(cond_str, variables_dict)
                            except Exception as e:
                                logger.warning(f"Could not parse guard '{cond_str}': {e}")
                                human_review_flags.append(f"Failed to parse guard condition '{cond_str}' in sentence {res.sentence_id}")
                                
                t = Transition(
                    id=f"t{t_counter:03d}",
                    from_state=f_state,
                    to_state=t_state,
                    event=event,
                    guard=guard_node,
                    source_sentence_ids=[res.sentence_id]
                )
                transitions.append(t)
                t_counter += 1
                
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

        return ibr, human_review_flags
