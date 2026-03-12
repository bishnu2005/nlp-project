import logging
from typing import List
from manual_to_uml.extraction.preprocessor import Sentence

logger = logging.getLogger(__name__)

def is_procedural_manual(sentences: List[Sentence]) -> bool:
    """
    Evaluates if a manual can bypass the LLM entirely based on
    strict procedural structures (e.g., 'Step X', 'If').
    """
    step_count = 0
    conditional_count = 0

    for s in sentences:
        text = s.text.lower()
        if text.startswith("step "):
            step_count += 1
            
        if "if " in text:
            conditional_count += 1

    if step_count >= 3:
        logger.info(f"[ProceduralDetector] Detected {step_count} step markers. Procedural mode enabled.")
        return True

    if conditional_count >= 2:
        logger.info(f"[ProceduralDetector] Detected {conditional_count} conditional markers. Procedural mode enabled.")
        return True

    return False
