import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class StateMapper:
    """
    Regex-based ontology rules mapping extraction contexts 
    to robust system modes instead of generic verbs.
    """
    def __init__(self):
        self.ontology_rules = [
            # Fault mappings
            (r'pressure.*above|pressure.*high|overpressure|psi.*exceed', 'fault_high_pressure'),
            (r'temperature.*exceed|temperature.*high|overheat|too hot', 'fault_high_temperature'),
            (r'leak|leakage|spill|fluid.*escape', 'fault_leak_detected'),
            (r'vibration|grinding|shaking|abnormal noise', 'fault_abnormal_vibration'),
            (r'emergency|immediate stop|e-stop|critical failure', 'fault_emergency_shutdown'),
            
            # Operational mappings
            (r'run|operate|maintain|normal|working|active|operating', 'running'),
            (r'inspect|check|verify|ensure|pre-start', 'inspection'),
            (r'start|begin|activate|initiate|power on', 'starting'),
            (r'cool|cooling|temperature drop', 'cooling'),
            (r'stop|shut down|terminate|disable|power off|shutdown', 'shutting_down'),
            (r'ready|standby|idle', 'ready')
        ]
        
        self.compiled_rules = [(re.compile(pattern, re.IGNORECASE), state) for pattern, state in self.ontology_rules]

    def map_to_state(self, context_text: str) -> str:
        """Evaluates textual context against Regex ontology dictionary"""
        if not context_text:
            return "running"  # Baseline fallback
            
        for regex, state_identifier in self.compiled_rules:
            if regex.search(context_text):
                return state_identifier
                
        # Default assumption if no domain words matched
        return "running"

def get_mapped_state(text: str) -> str:
    mapper = StateMapper()
    return mapper.map_to_state(text)
