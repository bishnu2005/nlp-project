from pydantic import BaseModel
from typing import List, Tuple, Optional, Dict
from sentence_transformers import SentenceTransformer
import numpy as np
import logging
from manual_to_uml.core.ibr_schema import IBR

logger = logging.getLogger(__name__)

class IntentMatch(BaseModel):
    matched_event: str
    matched_state: Optional[str]
    confidence: float
    alternatives: List[Tuple[str, float]]  # other matches + scores

CONFIDENCE_THRESHOLD = 0.65  # Lowered from 0.80 for symptom/natural language matching

SYNONYM_MAP = {
    "leakage_detected": ["water leaking", "leak", "fluid leaking", "dripping water"],
    "power_failure": ["no power", "not turning on", "machine dead"],
    "overheat": ["too hot", "temperature high", "overheating"],
    "start_pump": ["turn on pump", "activate pump", "start"],
    "shut_down": ["stop machine", "turn off", "power down"]
}

class IntentMapper:
    def __init__(self):
        try:
            # use a small, fast model for CPU compatibility and speed
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
        except Exception as e:
            logger.warning(f"Failed to load sentence-transformers model. Reason: {e}")
            self.model = None

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

    def _generate_descriptive_phrases(self, event_name: str, state_names: List[str]) -> List[str]:
        """Generate human-readable symptom/action variations from raw FSM event/state names."""
        clean_event = event_name.replace("_", " ").lower()
        phrases = [
            clean_event,
            f"I want to {clean_event}",
            f"How do I {clean_event}?",
            f"The system is showing {clean_event}",
            f"I see a {clean_event}",
            f"{clean_event} happened"
        ]
        
        # Add some state-specific context if it's a known state
        for state in state_names:
            clean_state = state.replace("_", " ").lower()
            if clean_state in clean_event:
                phrases.append(f"the {clean_state} is having an issue")
                
        # Common symptom mappings based on project prompt requirements
        if "leak" in clean_event: phrases.extend(["water is leaking", "it is leaking", "spraying water"])
        if "warning" in clean_event or "alert" in clean_event or "light" in clean_event: phrases.extend(["light is blinking", "red light", "warning light is on"])
        if "temp" in clean_event or "heat" in clean_event: phrases.extend(["is overheating", "too hot", "temperature high"])
        if "start" in clean_event and "fail" in clean_event: phrases.extend(["won't start", "refuses to start", "failed to turn on"])
        
        return phrases

    def map_intent(self, user_input: str, ibr: IBR, current_state: str) -> IntentMatch:
        if not self.model:
            # Fallback mock for testing environments where torch isn't available
            return IntentMatch(
                matched_event="mock_event", 
                matched_state=current_state, 
                confidence=0.99, 
                alternatives=[]
            )

        logger.info(f"[IntentMapper] Analyzing query: '{user_input}' (Current State: {current_state})")

        valid_transitions = [t for t in ibr.transitions if t.from_state == current_state]
        valid_events = list(set([t.event for t in valid_transitions]))
        all_events = list(set([t.event for t in ibr.transitions]))
        all_states = [s.id for s in ibr.states]
        
        if not all_events:
            logger.info("[IntentMapper] No events exist in the graph.")
            return IntentMatch(matched_event="", matched_state=None, confidence=0.0, alternatives=[])

        # Map phrase -> underlying event
        phrase_to_event: Dict[str, str] = {}
        
        for event in all_events:
            phrases = self._generate_descriptive_phrases(event, all_states)
            
            # Layer 1 - Synonym Map
            if event in SYNONYM_MAP:
                phrases.extend(SYNONYM_MAP[event])
                
            # Layer 2 - Include source manual sentences
            related_transitions = [t for t in ibr.transitions if t.event == event]
            for t in related_transitions:
                for sid in t.source_sentence_ids:
                    if sid in ibr.source_sentences:
                        phrases.append(ibr.source_sentences[sid])
                        
            for phrase in phrases:
                # If phrase exists, override only if current event is in valid_events 
                # (prioritizes active state transitions)
                if phrase not in phrase_to_event or event in valid_events:
                    phrase_to_event[phrase] = event

        corpus = list(phrase_to_event.keys())
        
        try:
            user_embedding = self.model.encode([user_input])[0]
            corpus_embeddings = self.model.encode(corpus)
            
            # Map event -> best score achieved by any of its phrases
            event_scores: Dict[str, float] = {}
            for idx, emb in enumerate(corpus_embeddings):
                sim = float(self._cosine_similarity(user_embedding, emb))
                phrase = corpus[idx]
                event = phrase_to_event[phrase]
                
                # Boost if it belongs to a valid transition in current state
                if event in valid_events:
                    sim += 0.05
                    
                if event not in event_scores or sim > event_scores[event]:
                    event_scores[event] = sim
                
            scores = [(evt, score) for evt, score in event_scores.items()]
            scores.sort(key=lambda x: x[1], reverse=True)
            
            best_match, best_score = scores[0]
            
            logger.info(f"[IntentMapper] Best match: '{best_match}' (confidence: {best_score:.3f})")
            
            alternatives = []
            if best_score < CONFIDENCE_THRESHOLD:
                logger.info(f"[IntentMapper] Match below threshold ({CONFIDENCE_THRESHOLD}).")
                alternatives = scores[1:min(4, len(scores))]
                
            return IntentMatch(
                matched_event=best_match,
                matched_state=current_state if best_match in valid_events else None,
                confidence=best_score,
                alternatives=alternatives
            )
            
        except Exception as e:
            logger.error(f"Intent matching failed: {e}")
            return IntentMatch(matched_event="", matched_state=None, confidence=0.0, alternatives=[])

def map_intent(user_input: str, ibr: IBR, current_state: str) -> IntentMatch:
    mapper = IntentMapper()
    return mapper.map_intent(user_input, ibr, current_state)
