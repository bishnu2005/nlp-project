from typing import Dict, Any, List
from manual_to_uml.core.ibr_schema import IBR
from manual_to_uml.chatbot.intent_mapper import IntentMatch, CONFIDENCE_THRESHOLD
from manual_to_uml.simulation.simulator_api import evaluate_guard_concrete

def resolve_response(intent: IntentMatch, ibr: IBR, current_state: str, variable_values: Dict[str, Any]) -> str:
    if intent.confidence < CONFIDENCE_THRESHOLD:
        if intent.alternatives:
            alt_list = ", ".join([f"'{a[0]}'" for a in intent.alternatives])
            return f"I am not sure what you mean. Did you mean to perform one of these actions: '{intent.matched_event}', {alt_list}?"
        else:
            return "I don't understand that instruction."
            
    # Check if event is valid from current state
    if intent.matched_state != current_state:
        # It means matched_event was found, but not for this state
        valid_events = list(set([t.event for t in ibr.transitions if t.from_state == current_state]))
        event_list = ", ".join(valid_events) if valid_events else "None (Terminal State)"
        return f"That action '{intent.matched_event}' is not valid in the current state '{current_state}'. Valid actions are: [{event_list}]."
        
    # Check guards
    possible_transitions = [t for t in ibr.transitions if t.from_state == current_state and t.event == intent.matched_event]
    
    valid_transition = None
    for t in possible_transitions:
        if t.guard:
            passed = evaluate_guard_concrete(t.guard, ibr.variables, variable_values)
            if passed:
                valid_transition = t
                break
        else:
            valid_transition = t
            break
            
    if not valid_transition:
        return f"The action '{intent.matched_event}' is currently blocked by guard conditions based on current variable values."
        
    next_state_name = valid_transition.to_state
    
    # Try to find target state name
    state_obj = next_state_name
    for s in ibr.states:
        if s.id == valid_transition.to_state:
            state_obj = s.name
            break
            
    action_text = f" and performing action '{valid_transition.action}'" if valid_transition.action else ""
    
    response = f"Executing '{intent.matched_event}'{action_text}. Transitioning to {state_obj}."
    return response
