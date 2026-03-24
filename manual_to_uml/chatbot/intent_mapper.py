import logging
from typing import List, Tuple, Optional, Dict
from pydantic import BaseModel
from rapidfuzz import fuzz
from manual_to_uml.core.ibr_schema import IBR

logger = logging.getLogger(__name__)

class IntentMatch(BaseModel):
    matched_event: str
    matched_state: Optional[str]
    confidence: float
    alternatives: List[Tuple[str, float]] = []
    is_meta: bool = False
    meta_response: Optional[str] = None

META_PATTERNS = [
    "how do i use",
    "how to use",
    "help",
    "what can you do",
    "what is this",
    "explain",
]

class IntentMapper:
    def map_intent(self, user_input: str, ibr: IBR, current_state: str) -> IntentMatch:
        user_query = user_input.lower().strip()
        logger.info(f"[IntentResolver] current_state: {current_state}")

        # Step 1: META query detection
        if any(pattern in user_query for pattern in META_PATTERNS):
            return IntentMatch(
                matched_event="",
                matched_state=None,
                confidence=1.0,
                is_meta=True,
                meta_response="I am an interactive assistant for this technical procedure. You can ask me to perform actions, describe system states, or ask 'help' to see what actions are available at the current step."
            )

        # Step 2: Get valid FSM transitions
        valid_events = list(set(t.event for t in ibr.transitions if t.from_state == current_state))
        logger.info(f"[IntentResolver] valid_events: {valid_events}")

        # Step 3: Keyword matching
        tokens = user_query.split()
        for event in valid_events:
            event_words = event.lower().replace("_", " ").split()
            if any(word in tokens for word in event_words):
                logger.info(f"[IntentResolver] keyword match: {event}")
                return IntentMatch(
                    matched_event=event,
                    matched_state=current_state,
                    confidence=1.0
                )

        # Step 4: Fuzzy matching
        best_event = None
        best_score = 0
        for event in valid_events:
            score = fuzz.partial_ratio(user_query, event.replace("_", " "))
            logger.info(f"[IntentResolver] fuzzy score: {score} for {event}")
            if score > 55 and score > best_score:
                best_score = score
                best_event = event

        if best_event:
            return IntentMatch(
                matched_event=best_event,
                matched_state=current_state,
                confidence=best_score / 100.0
            )

        # Step 5: Terminal state logic
        is_terminal = any(s.id == current_state and s.is_terminal for s in ibr.states)
        if is_terminal:
            return IntentMatch(
                matched_event="",
                matched_state=current_state,
                confidence=1.0,
                meta_response="This procedure has already completed. Restart from the first step if the issue persists."
            )

        # Step 6: Fallback response
        if valid_events:
            suggestions = "\n".join([f"* {e.replace('_', ' ')}" for e in valid_events])
            fallback_msg = f"I am not sure what you mean.\n\nValid actions from the current step are:\n\n{suggestions}"
        else:
            fallback_msg = "I am not sure what you mean, and there are no valid actions from the current state."

        return IntentMatch(
            matched_event="",
            matched_state=current_state,
            confidence=0.0,
            meta_response=fallback_msg
        )

def map_intent(user_input: str, ibr: IBR, current_state: str) -> IntentMatch:
    mapper = IntentMapper()
    return mapper.map_intent(user_input, ibr, current_state)
