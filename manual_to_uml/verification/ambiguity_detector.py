import logging
import json
import requests
from enum import Enum
from typing import List, Dict, Optional
from pydantic import BaseModel
from dotenv import load_dotenv
from manual_to_uml.extraction.preprocessor import Sentence

load_dotenv()

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3:8b"

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
        self.use_mock = False

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

    def _llm_check_batch(self, sentences: List[Sentence]) -> Dict[str, AmbiguityFlag]:
        if self.use_mock:
            # Mock LLM check
            flags = {}
            for sentence in sentences:
                if "mock_multiple" in sentence.text:
                    flags[sentence.id] = AmbiguityFlag(
                        ambiguity_type=AmbiguityType.MULTIPLE_PARSE,
                        sentence_id=sentence.id,
                        sentence_text=sentence.text,
                        confidence=0.9,
                        interpretations=["Do Action A then B", "Do Action A and B together"],
                        resolution="REQUIRES_HUMAN_CLARIFICATION"
                    )
            return flags

        prompt = f"""
        You are a linguistics ambiguity detector. Respond in strict JSON.
        Analyze the following batch of procedural instructions for ambiguity. 
        For each sentence, determine if it has MULTIPLE valid interpretations as a formal state machine instruction.
        Return ONLY a JSON array, where each element is: {{"sentence_id": "...", "ambiguous": bool, "interpretations": ["..."], "confidence": float}}
        
        Instructions:\n
        """
        for s in sentences:
            prompt += f"[{s.id}] {s.text}\n"
            
        try:
            response = requests.post(
                OLLAMA_URL,
                json={
                    "model": MODEL_NAME,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 1000
                    }
                },
                timeout=120
            )
            response.raise_for_status()
            result_str = response.json()["response"]
            
            # Strip Markdown fences if the LLM leaked them
            if result_str.startswith("```json"):
                result_str = result_str[7:-3].strip()
            elif result_str.startswith("```"):
                result_str = result_str[3:-3].strip()
            
            data_list = json.loads(result_str)
            if not isinstance(data_list, list):
                return {}
                
            flags_map = {}
            sent_map = {s.id: s.text for s in sentences}
            
            for data in data_list:
                if not isinstance(data, dict):
                    continue
                sid = data.get("sentence_id")
                if sid in sent_map and data.get("ambiguous", False) and data.get("confidence", 0.0) > 0.7:
                    flags_map[sid] = AmbiguityFlag(
                        ambiguity_type=AmbiguityType.MULTIPLE_PARSE,
                        sentence_id=sid,
                        sentence_text=sent_map[sid],
                        confidence=data.get("confidence"),
                        interpretations=data.get("interpretations", []),
                        resolution="REQUIRES_HUMAN_CLARIFICATION"
                    )
            return flags_map
        except Exception as e:
            logger.warning(f"LLM batch ambiguity check failed: {e}")
            return {}

    def detect(self, sentences: List[Sentence]) -> List[dict]:
        all_flags = []
        batch_size = 20
        
        for i in range(0, len(sentences), batch_size):
            batch = sentences[i:i + batch_size]
            
            # 1. Symbolic checks (fast)
            batch_flags = []
            for sent in batch:
                batch_flags.extend(self._symbolic_checks(sent))
                
            # 2. LLM Checks (batched)
            llm_flags_map = self._llm_check_batch(batch)
            
            for sent in batch:
                # Get symbolic flags for this sentence
                sent_sym_flags = [f for f in batch_flags if f.sentence_id == sent.id]
                
                # Deduplicate and add LLM flag
                if sent.id in llm_flags_map:
                    if not any(f.ambiguity_type == AmbiguityType.MULTIPLE_PARSE for f in sent_sym_flags):
                        sent_sym_flags.append(llm_flags_map[sent.id])
                        
                for f in sent_sym_flags:
                    all_flags.append(f.model_dump())
                    
        return all_flags

def detect_ambiguities(sentences: List[Sentence], api_key: str = None) -> List[dict]:
    detector = AmbiguityDetector(api_key)
    return detector.detect(sentences)
