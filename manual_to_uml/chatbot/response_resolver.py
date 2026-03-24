from typing import Dict, Any, List
from manual_to_uml.core.ibr_schema import IBR
from manual_to_uml.chatbot.intent_mapper import IntentMatch

def resolve_response(intent: IntentMatch, ibr: IBR, current_state: str, variable_values: Dict[str, Any]) -> str:
    """
    Deterministic FSM-aware response resolver.
    Ensures the chatbot only responds with valid transitions and never hallucinates.
    """
    
    # Handle meta queries or terminal state messages from IntentMapper
    if intent.is_meta or intent.matched_event == "":
        return intent.meta_response

    # Get valid transitions from current state
    valid_transitions = [t for t in ibr.transitions if t.from_state == current_state]
    valid_events = [t.event for t in valid_transitions]

    # Strict validation: check if matched_event exists in valid transitions
    if intent.matched_event not in valid_events:
        event_list = "\n".join([f"* {e.replace('_', ' ')}" for e in set(valid_events)])
        if event_list:
            return f"The action '{intent.matched_event.replace('_', ' ')}' is not valid in the current state.\n\nValid actions are:\n\n{event_list}"
        else:
            return f"The action '{intent.matched_event.replace('_', ' ')}' is not valid in the current state, and no actions are currently available."

    # If valid, return deterministic execution message
    # We use the raw event name from the FSM to ensure no hallucination
    return f"Executing action: {intent.matched_event}"
