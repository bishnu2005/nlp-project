import spacy
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class Sentence(BaseModel):
    id: str
    text: str
    original_index: int
    section: Optional[str] = None
    is_conditional: bool = False
    is_action: bool = False
    conditional_markers: List[str] = []
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = {
        "protected_namespaces": ()
    }

class Preprocessor:
    def __init__(self):
        try:
            self.nlp = spacy.load("en_core_web_sm")
            # We just need sentencizer and basic tagging for structural analysis here
        except Exception:
            import logging
            logging.getLogger(__name__).warning("Could not load en_core_web_sm, loading blank instead")
            self.nlp = spacy.blank("en")
            self.nlp.add_pipe("sentencizer")

        self.conditional_words = {"if", "when", "unless", "after", "once", "provided"}

    def _determine_section(self, text: str) -> Optional[str]:
        # Simple heuristic: if it's short and Ends with colon or all caps
        clean = text.strip()
        if len(clean) < 50:
            if clean.isupper() or clean.endswith(":"):
                return clean
            # Match Step X:
            if clean.lower().startswith("step "):
                return clean
        return None

    def _is_action(self, doc) -> bool:
        if len(doc) == 0:
            return False
            
        # Try to find the root verb
        for token in doc:
            if token.pos_ == "VERB" and token.dep_ == "ROOT":
                # Imperative verbs are often the first word or close to it with base form
                if token.i < 3 and token.tag_ in ("VB", "VBP"):
                    return True
                    
        # Fallback heuristic: starts with a base form verb (e.g., "Open", "Turn", "Check")
        first_word = doc[0]
        if first_word.pos_ == "VERB" and first_word.tag_ == "VB":
             return True
             
        # "Step 1: Ensure..." -> "Ensure..."
        for token in doc:
            if token.text.isalpha():
                if token.pos_ == "VERB" and token.tag_ == "VB":
                    return True
                break
                
        return False

    def preprocess_manual(self, text: str) -> List[Sentence]:
        # Split text into rough lines/blocks first to catch headers
        blocks = [b.strip() for b in text.split("\n") if b.strip()]
        
        sentences = []
        current_section = None
        s_idx = 1
        
        for block in blocks:
            # Check if block is a header
            section_guess = self._determine_section(block)
            if section_guess and len(block.split()) < 10:
                current_section = block
                # Still process it as a sentence just in case it contains instruction
            
            doc = self.nlp(block)
            for sent in doc.sents:
                sent_text = sent.text.strip()
                if not sent_text:
                    continue
                    
                # Find conditional markers
                sent_lower = sent_text.lower()
                markers = [w for w in self.conditional_words if w in sent_lower.split() or w + "," in sent_lower.split()]
                
                # Check for action
                is_act = self._is_action(sent)
                
                sentences.append(Sentence(
                    id=f"s{s_idx:03d}",
                    text=sent_text,
                    original_index=s_idx - 1,
                    section=current_section,
                    is_conditional=len(markers) > 0,
                    is_action=is_act,
                    conditional_markers=markers
                ))
                s_idx += 1
        from manual_to_uml.config import DEBUG_PIPELINE
        import logging
        if DEBUG_PIPELINE:
            logger = logging.getLogger(__name__)
            logger.info("[DEBUG] Sentences after preprocessing:")
            for s in sentences:
                logger.info({
                    "id": s.id,
                    "text": s.text,
                    "metadata": s.metadata
                })
                
        return sentences

def preprocess_manual(text: str) -> List[Sentence]:
    preprocessor = Preprocessor()
    return preprocessor.preprocess_manual(text)
