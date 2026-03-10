import os
import json
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import google.generativeai as genai
from dotenv import load_dotenv
from manual_to_uml.extraction.preprocessor import Sentence

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-2.5-flash")

logger = logging.getLogger(__name__)

class ExtractionResult(BaseModel):
    sentence_id: str
    states_mentioned: List[str] = []
    transitions_implied: List[Dict[str, str]] = [] # {from: str, to: str, event: str}
    guards_implied: List[Dict[str, str]] = [] # {transition_event: str, condition: str}
    events_implied: List[str] = []
    variables_mentioned: List[str] = []
    confidence: float
    ambiguity_flags: List[str] = []
    entry_action: Optional[str] = None

SYSTEM_PROMPT = """You are a formal methods extraction engine. Extract structured behavioral primitives from a batch of procedural text sentences. 
Return ONLY a valid JSON ARRAY of objects, where each object matches the ExtractionResult schema corresponding to an input sentence. No preamble, no explanation, no markdown fences."""

FEW_SHOT_EXAMPLES = """
Example:
Input:
[s001] Open the access panel by turning the latch counterclockwise.
[s002] If the filter indicator light is red, replace the filter.

Output:
[
  {
    "sentence_id": "s001",
    "states_mentioned": ["access_panel_closed", "access_panel_open"],
    "transitions_implied": [{"from": "access_panel_closed", "to": "access_panel_open", "event": "turn_latch_counterclockwise"}],
    "guards_implied": [],
    "events_implied": ["turn_latch_counterclockwise"],
    "variables_mentioned": [],
    "confidence": 0.9,
    "ambiguity_flags": []
  },
  {
    "sentence_id": "s002",
    "states_mentioned": ["filter_nominal", "filter_replaced"],
    "transitions_implied": [{"from": "filter_nominal", "to": "filter_replaced", "event": "replace_filter"}],
    "guards_implied": [{"transition_event": "replace_filter", "condition": "filter_indicator_light == 'red'"}],
    "events_implied": ["replace_filter"],
    "variables_mentioned": ["filter_indicator_light"],
    "confidence": 0.85,
    "ambiguity_flags": []
  }
]
"""

class LLMExtractor:
    def __init__(self, api_key: Optional[str] = None):
        # We allow fallback to a mock for initial disconnected testing
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
        self.use_mock = not self.api_key

    def _call_llm(self, prompt: str) -> str:
        if self.use_mock:
            # Mock mode - deterministic return for testing
            mock_resp = [{
                "sentence_id": "mock",
                "states_mentioned": ["state_a", "state_b"],
                "transitions_implied": [{"from": "state_a", "to": "state_b", "event": "mock_event"}],
                "guards_implied": [],
                "events_implied": ["mock_event"],
                "variables_mentioned": ["mock_var"],
                "confidence": 0.8,
                "ambiguity_flags": []
            }]
            return json.dumps(mock_resp)

        try:
            full_prompt = SYSTEM_PROMPT + "\n\n" + FEW_SHOT_EXAMPLES + "\n\n" + prompt
            response = model.generate_content(full_prompt)
            output = response.text
            return output
        except Exception as e:
            logger.error(f"LLM Call failed: {e}")
            raise e

    def extract_batch(self, sentences: List[Sentence]) -> List[ExtractionResult]:
        import time
        prompt = "Input Batch:\n" + "\n".join([f"[{s.id}] {s.text}" for s in sentences])
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                result_str = self._call_llm(prompt)
                
                # Strip Markdown fences if the LLM leaked them despite prompt instructions
                if result_str.startswith("```json"):
                    result_str = result_str[7:-3].strip()
                elif result_str.startswith("```"):
                    result_str = result_str[3:-3].strip()
                    
                data_list = json.loads(result_str)
                if not isinstance(data_list, list):
                    raise ValueError("Output must be a JSON array.")
                
                results = []
                # Ensure we only process valid dicts
                for data in data_list:
                    if isinstance(data, dict):
                        # Graceful fallback for missing fields in nested structures
                        if "sentence_id" not in data:
                            continue
                        results.append(ExtractionResult(**data))
                return results
                
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Failed to parse LLM output (Attempt {attempt+1}/{max_retries}): {e}")
                prompt += f"\n\nERROR IN PREVIOUS ATTEMPT: Output must be strictly valid JSON ARRAY matching the schema. Error was: {e}. Do not include markdown codeblocks."
                time.sleep(2)
                
        # If all retries fail, return empty stubs
        logger.error(f"Failed to extract primitives for batch after {max_retries} attempts.")
        return [ExtractionResult(
            sentence_id=s.id,
            confidence=0.0,
            ambiguity_flags=["LLM_EXTRACTION_FAILED"]
        ) for s in sentences]

    def extract_all(self, sentences: List[Sentence]) -> List[ExtractionResult]:
        import time
        results = []
        batch_size = 50 # Batch processing to avoid Gemini 5 RPM limit
        
        for i in range(0, len(sentences), batch_size):
            batch = sentences[i:i + batch_size]
            logger.info(f"Extracting batch {i//batch_size + 1}/{((len(sentences) - 1)//batch_size) + 1} (size {len(batch)})...")
            
            try:
                batch_results = self.extract_batch(batch)
                results.extend(batch_results)
            except Exception as e:
                logger.error(f"Batch extraction failed: {e}")
                
            # API Rate limit protection (Gemini free tier: ~5 RPM)
            # Sleep 12.5 seconds between batches to ensure we stay under the limit
            if i + batch_size < len(sentences):
                logger.info("Sleeping for 12.5 seconds to respect API rate limits...")
                time.sleep(12.5)
                
        return results
