import re
from typing import List, Dict, Tuple, Optional
from manual_to_uml.extraction.preprocessor import Sentence

class ConditionDetector:
    def __init__(self):
        self.condition_patterns = [
            r"if\s+(.*)",
            r"when\s+(.*)",
            r"should\s+(.*)",
            r"in case of\s+(.*)",
            r"assuming\s+(.*)"
        ]
        
    def detect_conditions(self, sentence: Sentence) -> List[str]:
        text_lower = sentence.text.lower()
        guards = []
        for pattern in self.condition_patterns:
            matches = re.finditer(pattern, text_lower)
            for match in matches:
                # Extract the condition clause (heuristic: up to a comma or end of sentence)
                full_clause = match.group(1)
                condition = full_clause.split(',')[0].strip()
                if condition:
                    guards.append(condition)
        return guards

    def extract_events(self, sentence: Sentence) -> List[str]:
        # Very simple heuristic: anything after a "then" or a comma following a condition
        # For now, rely on LLM or simple verb extraction
        return []

def detect_rules(sentence: Sentence) -> Dict[str, List[str]]:
    detector = ConditionDetector()
    guards = detector.detect_conditions(sentence)
    events = detector.extract_events(sentence)
    from manual_to_uml.config import DEBUG_PIPELINE
    import logging
    if DEBUG_PIPELINE and guards:
        logger = logging.getLogger(__name__)
        for guard in guards:
            logger.info("[DEBUG] Condition detected")
            logger.info({
                "sentence_id": sentence.id,
                "condition": guard,
                "action": "",
                "guard": guard
            })
            
    return {
        "guards": guards,
        "events": events
    }
