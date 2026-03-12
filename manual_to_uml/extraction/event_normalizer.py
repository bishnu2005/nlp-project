import logging
from typing import Dict, List, Optional
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

class EventNormalizer:
    """
    Standardizes varied English phrasing ("turn on pump", "start pumping system")
    into a consolidated formal method naming convention ("start_pump").
    """
    def __init__(self):
        # A simple hand-curated synonym base to act as a core clustering anchor
        self.synonym_base = {
            "start": ["activate", "turn_on", "initiate", "begin", "enable"],
            "stop": ["deactivate", "turn_off", "shutdown", "halt", "disable", "end"],
            "check": ["inspect", "verify", "monitor", "observe", "test"],
            "replace": ["swap", "change", "renew"],
            "increase": ["raise", "boost", "elevate"],
            "decrease": ["lower", "reduce", "drop"]
        }
        
    def normalize(self, event_name: str, existing_events: Optional[List[str]] = None) -> str:
        if not event_name:
            return "unknown_event"
            
        normalized = event_name.lower().strip()
        
        # 1. Structural normalization (snake_case conversion)
        normalized = normalized.replace(" ", "_").replace("-", "_")
        
        # 2. Verb Normalization via hardcoded synonym dictionary mapping
        parts = normalized.split("_")
        if parts:
            verb = parts[0]
            for anchor, syns in self.synonym_base.items():
                if verb in syns:
                    parts[0] = anchor
                    break
            normalized = "_".join(parts)
            
        # 3. Simple Stop-word filtering for clearer diagrams ("turn_on_the_pump" -> "turn_on_pump")
        stop_words = ["the", "a", "an", "system", "unit", "device"]
        filtered_parts = [p for p in normalized.split("_") if p not in stop_words]
        if filtered_parts:
            normalized = "_".join(filtered_parts)
            
        # 4. Fuzzy Matching against existing known event identifiers to prevent fragmentation
        # e.g., mapping "start_cooling_system" back to an already registered "start_cooling"
        if existing_events:
            best_match = None
            highest_ratio = 0.0
            for existing in existing_events:
                ratio = SequenceMatcher(None, normalized, existing).ratio()
                # 0.85 indicates a very strong typo or grammatical similarity
                if ratio > 0.85 and ratio > highest_ratio:
                    best_match = existing
                    highest_ratio = ratio
                    
            if best_match:
                logger.debug(f"[EventNormalizer] Clustered '{event_name}' -> existing '{best_match}' (sim: {highest_ratio:.2f})")
                return best_match

        return normalized

def normalize_events_in_extractions(extractions: List['ExtractionResult']) -> List['ExtractionResult']:
    normalizer = EventNormalizer()
    global_event_registry = []
    
    for ext in extractions:
        normalized_list = []
        for raw_event in ext.events_implied:
            clean = normalizer.normalize(raw_event, global_event_registry)
            if clean not in global_event_registry:
                global_event_registry.append(clean)
            normalized_list.append(clean)
            
        ext.events_implied = list(set(normalized_list))
        
        # Also clean up transitions
        for t in ext.transitions_implied:
            if "event" in t:
                t["event"] = normalizer.normalize(t["event"], global_event_registry)
                
    return extractions
