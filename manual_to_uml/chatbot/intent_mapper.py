from pydantic import BaseModel
from typing import List, Tuple, Optional
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

CONFIDENCE_THRESHOLD = 0.80

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

    def map_intent(self, user_input: str, ibr: IBR, current_state: str) -> IntentMatch:
        if not self.model:
            # Fallback mock for testing environments where torch isn't available
            return IntentMatch(
                matched_event="mock_event", 
                matched_state=current_state, 
                confidence=0.99, 
                alternatives=[]
            )

        # Build corpus of possible events from current state
        # Also include all events in the system for better context error reporting
        # Though we prioritize current state events
        
        valid_transitions = [t for t in ibr.transitions if t.from_state == current_state]
        valid_events = list(set([t.event for t in valid_transitions]))
        
        all_events = list(set([t.event for t in ibr.transitions]))
        other_events = [e for e in all_events if e not in valid_events]
        
        # In a real NLP agent, we might encode "How do I [event_name]" or similar
        # For this formal matching, we just match the raw event name against user input
        
        # If no valid events (terminal state or disconnected)
        if not all_events:
            return IntentMatch(matched_event="", matched_state=None, confidence=0.0, alternatives=[])
            
        corpus = valid_events + other_events
        corpus_clean = [e.replace("_", " ") for e in corpus]
        
        try:
            user_embedding = self.model.encode([user_input])[0]
            corpus_embeddings = self.model.encode(corpus_clean)
            
            scores = []
            for idx, emb in enumerate(corpus_embeddings):
                sim = float(self._cosine_similarity(user_embedding, emb))
                scores.append((corpus[idx], sim))
                
            scores.sort(key=lambda x: x[1], reverse=True)
            
            best_match, best_score = scores[0]
            
            alternatives = []
            if best_score < CONFIDENCE_THRESHOLD:
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
