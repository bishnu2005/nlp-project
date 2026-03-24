import spacy
import logging
from typing import Optional, Tuple
from manual_to_uml.extraction.preprocessor import Sentence

logger = logging.getLogger(__name__)

class EventExtractor:
    """
    Extracts events offline locally without LLM hallucination by locating 
    the core ROOT verb and its direct object in English dependency trees.
    """
    def __init__(self):
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except Exception as e:
            logger.warning(f"Failed to load spaCy model: {e}. Event extraction will fallback to simple splitting.")
            self.nlp = None

    def _normalize_event_name(self, verb: str, obj: str) -> str:
        """Converts extracted words into a clean, snake_case event trigger"""
        v = verb.lower().strip()
        o = obj.lower().strip()
        
        # English Grammar standardizing: Press START button -> start_button_pressed
        if v in ["press", "hit", "push"]:
            return f"{o.replace(' ', '_')}_{v}ed"
        
        return f"{v}_{o.replace(' ', '_')}"

    def extract_event(self, text: str) -> Optional[str]:
        if not self.nlp:
            words = text.split()
            if len(words) >= 2:
                return self._normalize_event_name(words[0], words[1])
            return None

        doc = self.nlp(text)
        
        # Pre-filter: if text is extremely short, it might just be the event itself ("Start pump")
        if len(doc) <= 3:
            verb = [t for t in doc if t.pos_ == "VERB"]
            obj = [t for t in doc if t.pos_ in ("NOUN", "PROPN")]
            if verb and obj:
                return self._normalize_event_name(verb[0].lemma_, obj[0].text)
            
        # Recursive Descent Dependency matching for ROOT verb -> DOBJ
        # Example: "Press the START button"
        # ROOT: Press (VERB)
        #  └─ dobj: button (NOUN)
        #      └─ compound: START (PROPN)
        for token in doc:
            if token.pos_ == "VERB":
                # Find direct object attached to this verb
                for child in token.children:
                    if child.dep_ in ("dobj", "pobj"):
                        # Build the full sub-object string (e.g. "START button")
                        modifiers = [c.text for c in child.children if c.dep_ in ("amod", "compound", "nummod")]
                        obj_text = " ".join(modifiers + [child.text])
                        return self._normalize_event_name(token.lemma_, obj_text)
                        
        # Fallback heuristic: First VERB + First NOUN
        verbs = [t.lemma_ for t in doc if t.pos_ == "VERB"]
        nouns = [t.text for t in doc if t.pos_ in ("NOUN", "PROPN")]
        if verbs and nouns:
            return self._normalize_event_name(verbs[0], nouns[0])

        return None

def extract_deterministic_event(sentence: Sentence) -> Optional[str]:
    extractor = EventExtractor()
    event = extractor.extract_event(sentence.text)
    from manual_to_uml.config import DEBUG_PIPELINE
    if DEBUG_PIPELINE and event:
        logger.info("[DEBUG] Event extraction")
        logger.info({
            "sentence_id": sentence.id,
            "event": event,
            "source": "spacy"
        })
    return event
