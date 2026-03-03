import re
from typing import Dict, List, Optional
from manual_to_uml.core.ibr_schema import VariableType
from manual_to_uml.extraction.llm_extractor import ExtractionResult
import logging

logger = logging.getLogger(__name__)

class SymbolicNormalizer:
    def __init__(self):
        self.stop_words = {"the", "a", "an", "is", "are", "was", "were", "to", "in", "on", "at"}
        
    def normalize_state_name(self, name: str) -> str:
        # Lowercase and replace spaces/hyphens with underscores
        clean = name.lower().replace("-", "_")
        words = re.findall(r'\b\w+\b', clean)
        
        # Remove stop words
        filtered = [w for w in words if w not in self.stop_words]
        
        # Join with underscores
        return "_".join(filtered) if filtered else clean.replace(" ", "_")
        
    def normalize_operator(self, op: str) -> str:
        op_map = {
            "greater than": ">",
            "more than": ">",
            "exceeds": ">",
            "less than": "<",
            "fewer than": "<",
            "under": "<",
            "equals": "==",
            "equal to": "==",
            "is": "==",
            "at least": ">=",
            "greater than or equal to": ">=",
            "at most": "<=",
            "less than or equal to": "<="
        }
        return op_map.get(op.lower().strip(), op.strip())
        
    def infer_type(self, var_name: str) -> VariableType:
        name_lower = var_name.lower()
        if any(kw in name_lower for kw in ["temperature", "pressure", "level", "threshold", "rate", "distance", "weight"]):
            return VariableType.FLOAT
        if any(kw in name_lower for kw in ["count", "number", "attempts", "duration", "time", "index"]):
            return VariableType.INT
        if any(kw in name_lower for kw in ["status", "mode", "state", "type"]):
            return VariableType.ENUM
        if any(kw in name_lower for kw in ["flag", "enabled", "active", "is_", "has_", "requires"]):
            return VariableType.BOOLEAN
        return VariableType.STRING

    def normalize_results(self, results: List[ExtractionResult]) -> List[ExtractionResult]:
        for res in results:
            # Normalize States
            res.states_mentioned = [self.normalize_state_name(s) for s in res.states_mentioned]
            
            # Normalize Transitions
            for t in res.transitions_implied:
                t["from"] = self.normalize_state_name(t["from"])
                t["to"] = self.normalize_state_name(t["to"])
                
            # Events and Variables are kept mostly as-is, but we could normalize them
            res.events_implied = [e.lower().replace(" ", "_").replace("-", "_") for e in res.events_implied]
            
            # For variables, we infer their type and registry but we do that in Assembler
            
        return results

    def find_synonymous_states(self, states: List[str]) -> List[str]:
        # Simple heuristic: if one state name is completely contained in another, 
        # or they share a prominent keyword
        # E.g. "system_ready" vs "ready_state"
        flags = []
        for i in range(len(states)):
            for j in range(i + 1, len(states)):
                s1, s2 = states[i], states[j]
                w1 = set(s1.split("_"))
                w2 = set(s2.split("_"))
                
                # Check for significant overlap
                overlap = w1.intersection(w2)
                if len(overlap) > 0 and len(overlap) >= min(len(w1), len(w2)) * 0.5:
                    flags.append(f"Potential duplicate states: '{s1}' and '{s2}' share keywords.")
                    
        return list(set(flags))
