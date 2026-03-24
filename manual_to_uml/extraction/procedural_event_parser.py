import re
import spacy
from typing import Optional
from manual_to_uml.extraction.preprocessor import Sentence

try:
    nlp = spacy.load("en_core_web_sm")
except Exception:
    import logging
    logging.getLogger(__name__).warning("Could not load en_core_web_sm, using blank.")
    nlp = spacy.blank("en")

def parse_event(sentence: Sentence) -> str:
    """
    Deterministically constructs action verb_noun tokens using spaCy
    dependency trees instead of LLM inference.
    """
    doc = nlp(sentence.text)
    
    root = None
    obj = None

    for token in doc:
        if token.dep_ == "ROOT":
            root = token.lemma_

        if token.dep_ in ("dobj", "pobj"):
            obj = token.lemma_

    if root and obj:
        return f"{root}_{obj}"

    if root:
        return root

    return "unknown_event"
