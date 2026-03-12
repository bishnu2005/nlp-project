import re
import logging
from typing import List, Optional
from manual_to_uml.extraction.preprocessor import Sentence

logger = logging.getLogger(__name__)

class SectionParser:
    """
    Scans sequential sentences for Regex headers (e.g., '1. Normal Operation')
    and persists them as semantic metadata to ground abstracted states mathematically.
    """
    def __init__(self):
        # Match '1. Heading' or '1.1 Heading' etc
        self.heading_regex = re.compile(r"^[\d\.]+\s+([A-Z].+)$")

    def identify_section_state(self, sentence: Sentence) -> Optional[str]:
        match = self.heading_regex.match(sentence.text)
        if match:
            # Extract header text and format into FSM mode identifier
            raw_heading = match.group(1).strip()
            # Convert "Pre-Start Inspection" -> "Pre_Start_Inspection"
            state_name = raw_heading.replace(" ", "_").replace("-", "_").title()
            logger.info(f"[SectionParser] Detected state anchor: {state_name} from header '{raw_heading}'")
            return state_name
        return None

def parse_manual_sections(sentences: List[Sentence]) -> List[Sentence]:
    parser = SectionParser()
    current_section = "Initial"
    
    for sent in sentences:
        detected = parser.identify_section_state(sent)
        if detected:
            current_section = detected
            
        # Stamp metadata directly onto the sentence object for later processing
        # This allows state inference downstream without relying on LLM guesses
        if getattr(sent, "metadata", None) is None:
            sent.metadata = {}
        sent.metadata['section'] = current_section
    from manual_to_uml.config import DEBUG_PIPELINE
    if DEBUG_PIPELINE:
        logger.info("[DEBUG] Section parser output")
        for s in sentences:
            logger.info({
                "id": s.id,
                "text": s.text,
                "section": s.metadata.get("section")
            })
            
    return sentences
