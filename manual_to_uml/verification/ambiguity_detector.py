import os
import json
import logging
from enum import Enum
from typing import List, Dict, Optional
from pydantic import BaseModel
import google.generativeai as genai
from dotenv import load_dotenv
from manual_to_uml.extraction.preprocessor import Sentence

load_dotenv()

logger = logging.getLogger(__name__)

class AmbiguityType(str, Enum):
    VAGUE_QUANTIFIER = "VAGUE_QUANTIFIER"
    REFERENTIAL = "REFERENTIAL"
    SCOPE = "SCOPE"
    IMPLICIT_BRANCHING = "IMPLICIT_BRANCHING"
    MULTIPLE_PARSE = "MULTIPLE_PARSE"

class AmbiguityFlag(BaseModel):
    ambiguity_type: AmbiguityType
    sentence_id: str
    sentence_text: str
    confidence: float
    interpretations: List[str]
    resolution: str = "REQUIRES_HUMAN_CLARIFICATION"

class AmbiguityDetector:
    def __init__(self, api_key: str = None):
        self.vague_terms = [
            "wait until stable", "sufficient", "adequate", "appropriate", 
            "as needed", "if necessary", "enough", "normal", "slowly", "quickly"
        ]
        self.implicit_branch_terms = [
            "otherwise", "if necessary", "as needed", "in case of", "alternatively"
        ]
        
        resolved_key = api_key
        if resolved_key:
            genai.configure(api_key=resolved_key)
            self.model = genai.GenerativeModel("gemini-2.5-flash")
        else:
            self.model = None

    def _symbolic_checks(self, sentence: Sentence) -> List[AmbiguityFlag]:
        flags = []
        text_lower = sentence.text.lower()
        
        # 1. Vague Quantifier
        for term in self.vague_terms:
            if term in text_lower:
                flags.append(AmbiguityFlag(
                    ambiguity_type=AmbiguityType.VAGUE_QUANTIFIER,
                    sentence_id=sentence.id,
                    sentence_text=sentence.text,
                    confidence=0.9,
                    interpretations=[],
                    resolution="Replace vague term with a measurable guard condition (e.g., '> 50 units')."
                ))
                break # One vague flag per sentence is enough
                
        # 2. Implicit Branching
        if not sentence.is_conditional: # Only flag if it doesn't already have explicit conditional markers
            for term in self.implicit_branch_terms:
                if term in text_lower:
                    flags.append(AmbiguityFlag(
                        ambiguity_type=AmbiguityType.IMPLICIT_BRANCHING,
                        sentence_id=sentence.id,
                        sentence_text=sentence.text,
                        confidence=0.85,
                        interpretations=[],
                        resolution="Clarify the exact condition for this alternative path."
                    ))
                    break
                    
        return flags

    def _llm_check(self, sentence: Sentence) -> Optional[AmbiguityFlag]:
        if not self.model:
            # Mock LLM check
            if "mock_multiple" in sentence.text:
                return AmbiguityFlag(
                    ambiguity_type=AmbiguityType.MULTIPLE_PARSE,
                    sentence_id=sentence.id,
                    sentence_text=sentence.text,
                    confidence=0.9,
                    interpretations=["Do Action A then B", "Do Action A and B together"],
                    resolution="REQUIRES_HUMAN_CLARIFICATION"
                )
            return None

        prompt = f"""
        You are a linguistics ambiguity detector. Respond in strict JSON.
        Analyze the following procedural instruction for ambiguity. 
        Does this sentence have multiple valid interpretations as a formal state machine instruction?
        If yes, list them.
        Return JSON format: {{"ambiguous": bool, "interpretations": ["..."], "confidence": float}}
        
        Instruction: "{sentence.text}"
        """
        
        try:
            response = self.model.generate_content(prompt)
            result_str = response.text
            
            # Strip Markdown fences if the LLM leaked them
            if result_str.startswith("```json"):
                result_str = result_str[7:-3].strip()
            elif result_str.startswith("```"):
                result_str = result_str[3:-3].strip()
            
            data = json.loads(result_str)
            
            if data.get("ambiguous", False) and data.get("confidence", 0.0) > 0.7:
                return AmbiguityFlag(
                    ambiguity_type=AmbiguityType.MULTIPLE_PARSE,
                    sentence_id=sentence.id,
                    sentence_text=sentence.text,
                    confidence=data.get("confidence"),
                    interpretations=data.get("interpretations", []),
                    resolution="REQUIRES_HUMAN_CLARIFICATION"
                )
        except Exception as e:
            logger.warning(f"LLM ambiguity check failed for {sentence.id}: {e}")
            
        return None

    def detect(self, sentences: List[Sentence]) -> List[dict]:
        all_flags = []
        
        for sent in sentences:
            sentence_flags = self._symbolic_checks(sent)
            
            # Run LLM check
            llm_flag = self._llm_check(sent)
            if llm_flag:
                # Deduplicate if LLM caught same issue symbolically (simplified deduplication)
                if not any(f.ambiguity_type == AmbiguityType.MULTIPLE_PARSE for f in sentence_flags):
                    sentence_flags.append(llm_flag)
                    
            for f in sentence_flags:
                all_flags.append(f.model_dump())
                
        return all_flags

def detect_ambiguities(sentences: List[Sentence], api_key: str = None) -> List[dict]:
    detector = AmbiguityDetector(api_key)
    return detector.detect(sentences)
