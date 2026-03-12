import os
import json
import logging
import requests
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from dotenv import load_dotenv
from manual_to_uml.extraction.preprocessor import Sentence

load_dotenv()

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "phi3:mini"

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
    source_sentence_ids: List[str] = []

SYSTEM_PROMPT = """You are a formal methods extraction engine. Extract structured behavioral primitives from a batch of procedural text sentences. 
Respond only with JSON. No explanation.
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
        # API key is ignored for local Ollama, kept for interface compatibility
        self.use_mock = False

    def _safe_json_parse(self, raw_text: str) -> Any:
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            pass

        import re
        # Look for [ ... ] or { ... } anywhere in the text
        json_pattern = re.compile(r'(\[.*\]|\{.*\})', re.DOTALL)
        match = json_pattern.search(raw_text)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass
        raise ValueError("Could not extract coherent JSON objects from response.")

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
            response = requests.post(
                OLLAMA_URL,
                json={
                    "model": MODEL_NAME,
                    "prompt": full_prompt,
                    "format": "json",
                    "stream": False,
                    "options": {
                        "temperature": 0,
                        "num_predict": 200,
                        "num_ctx": 2048,
                        "top_k": 1
                    }
                },
                timeout=120
            )
            response.raise_for_status()
            return response.json()["response"]
        except Exception as e:
            logger.error(f"Local LLM Call failed: {e}")
            raise e

    def extract_batch(self, sentences: List[Sentence], retry_count: int = 0) -> List[ExtractionResult]:
        import time
        if not sentences: return []
        
        MAX_RETRIES = 3
        if retry_count >= MAX_RETRIES:
            logger.error(f"Atomic chunk extraction failed after {MAX_RETRIES} recursive retries. Marking ambiguous.")
            return [ExtractionResult(
                sentence_id=sentences[0].id,
                confidence=0.0,
                ambiguity_flags=["LLM_EXTRACTION_FAILED"]
            )]
            
        prompt = "Input Batch:\n" + "\n".join([f"[{s.id}] {s.text}" for s in sentences])
        
        try:
            result_str = self._call_llm(prompt)
            data_list = self._safe_json_parse(result_str)
            
            if not isinstance(data_list, list):
                if isinstance(data_list, dict):
                    data_list = [data_list]
                else:
                    raise ValueError("Output must be a JSON array.")
            
            results = []
            for data in data_list:
                if isinstance(data, dict):
                    if "sentence_id" not in data: continue
                    results.append(ExtractionResult(**data))
            return results
            
        except Exception as e:
            logger.warning(f"Failed to parse LLM output. Chunk size was {len(sentences)}. Error: {e}")
            if len(sentences) > 1:
                mid = len(sentences) // 2
                logger.info(f"Retrying with smaller chunks: {mid} and {len(sentences) - mid}")
                time.sleep(1)
                first_half = self.extract_batch(sentences[:mid], retry_count + 1)
                second_half = self.extract_batch(sentences[mid:], retry_count + 1)
                return first_half + second_half
            else:
                return self.extract_batch(sentences, retry_count + 1)

    def should_use_llm(self, sentence: Sentence) -> bool:
        if sentence.is_action:
            return False
        if sentence.is_conditional:
            return False
        if sentence.section and sentence.section.lower().startswith("step"):
            return False
        if getattr(sentence, "metadata", {}).get("section", "").lower().startswith("step"):
            return False
        return True

    def extract_all(self, sentences: List[Sentence]) -> List[ExtractionResult]:
        from manual_to_uml.extraction.condition_detector import detect_rules
        from manual_to_uml.extraction.event_extractor import extract_deterministic_event
        from manual_to_uml.extraction.section_parser import parse_manual_sections
        from manual_to_uml.extraction.event_normalizer import normalize_events_in_extractions
        import concurrent.futures
        
        # 1. Pre-process sections to assign operational modes
        sentences = parse_manual_sections(sentences)
        
        rule_results = []
        llm_queue = []
        
        # 2. Pre-pass classifier routing
        for s in sentences:
            if not self.should_use_llm(s):
                rules = detect_rules(s)
                # Ensure spaCy gets a shot at extracting the main verb
                spacy_event = extract_deterministic_event(s)
                if spacy_event and spacy_event not in rules["events"]:
                    rules["events"].append(spacy_event)
                    
                guards_implied = []
                events_implied = rules["events"]
                
                if rules["guards"]:
                    evts = rules["events"] if rules["events"] else ["evaluate_condition"]
                    for g in rules["guards"]:
                        for e in evts:
                            guards_implied.append({"transition_event": e, "condition": g})
                            if e not in events_implied:
                                events_implied.append(e)
                
                # Read section metadata if available
                states_ment = [s.metadata['section']] if getattr(s, 'metadata', None) and 'section' in s.metadata else []
                
                res = ExtractionResult(
                    sentence_id=s.id,
                    states_mentioned=states_ment,
                    guards_implied=guards_implied,
                    events_implied=events_implied,
                    confidence=1.0,
                    source_sentence_ids=[s.id]
                )
                rule_results.append(res)
            else:
                llm_queue.append(s)
                
        logger.info(f"Rule parsed: {len(rule_results)}")
        logger.info(f"Sent to LLM: {len(llm_queue)}")
        
        results = list(rule_results)
        CHUNK_SIZE = 5
        
        llm_chunks = []
        for i in range(0, len(llm_queue), CHUNK_SIZE):
            llm_chunks.append(llm_queue[i:i + CHUNK_SIZE])
                
        # 3. Parallel Processing for LLM Fallbacks
        if llm_chunks:
            logger.info(f"Firing {len(llm_chunks)} fallback chunks to Ollama in parallel...")
            max_workers = min(4, os.cpu_count() or 4)
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_chunk = {executor.submit(self.extract_batch, chunk): chunk for chunk in llm_chunks}
                
                for future in concurrent.futures.as_completed(future_to_chunk):
                    try:
                        batch_results = future.result()
                        results.extend(batch_results)
                    except Exception as e:
                        logger.error(f"Parallel chunk extraction failed: {e}")
                        
        # 4. Global Normalization Sweep
        results = normalize_events_in_extractions(results)
        return results
