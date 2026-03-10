import logging
from typing import List, Dict, Optional
from manual_to_uml.extraction.llm_extractor import ExtractionResult
from manual_to_uml.extraction.preprocessor import Sentence

logger = logging.getLogger(__name__)

class StateAbstractor:
    def __init__(self):
        self.roles = ["initial", "operating", "waiting", "error", "terminal"]
        self.min_states = 4
        self.max_states = 12

    def _get_role(self, text: str) -> str:
        text_lower = text.lower()
        if any(w in text_lower for w in ["error", "fail", "fault", "leak", "hazard", "damage", "alarm", "replace"]):
            return "error"
        if any(w in text_lower for w in ["shut down", "stop", "end", "terminate", "finish", "disconnect"]):
            return "terminal"
        if any(w in text_lower for w in ["wait", "until", "pause", "check", "monitor", "observe", "verify", "inspect"]):
            return "waiting"
        if any(w in text_lower for w in ["start", "begin", "initial", "ensure", "prepare", "connect", "power"]):
            return "initial"
        return "operating"

    def _merge_blocks(self, blocks: List[Dict]) -> List[Dict]:
        """Merge blocks sequentially to obey budget."""
        # Simple frequency compression: group identical non-consecutive roles if over budget
        merged = []
        for role in self.roles:
            combined = {"role": role, "extractions": []}
            for b in blocks:
                if b["role"] == role:
                    combined["extractions"].extend(b["extractions"])
            if combined["extractions"]:
                merged.append(combined)
        return merged

    def abstract(self, extractions: List[ExtractionResult], sentences: List[Sentence]) -> List[ExtractionResult]:
        sent_map = {s.id: s.text for s in sentences}
        
        # 1. Classify & Group consecutive extractions with the same role
        blocks = []
        current_block = []
        current_role = None
        
        for ext in extractions:
            text = sent_map.get(ext.sentence_id, "")
            role = self._get_role(text)
            
            if role == current_role:
                current_block.append(ext)
            else:
                if current_block:
                    blocks.append({"role": current_role, "extractions": current_block})
                current_block = [ext]
                current_role = role
                
        if current_block:
            blocks.append({"role": current_role, "extractions": current_block})
            
        # Fallback if no extractions passed through (or extractions was empty)
        if not blocks:
            logger.warning("Abstraction yielded 0 blocks. Creating a fallback Initial state to satisfy IBR schema.")
            fallback_res = ExtractionResult(
                sentence_id=sentences[0].id if sentences else "b0",
                states_mentioned=["Initial"],
                confidence=1.0
            )
            blocks.append({"role": "initial", "extractions": [fallback_res]})
            
        # 2. State Budget Limiter
        if len(blocks) > self.max_states:
             logger.info(f"State budget exceeded ({len(blocks)}). Merging based on role to {len(self.roles)} states max.")
             blocks = self._merge_blocks(blocks)
             
        # 3. Build Abstract Extractions (1 per Block)
        abstracted = []
        for i, b in enumerate(blocks):
            role = b["role"]
            state_name = f"{role.title()}_{i}" if len(blocks) <= self.max_states else role.title()
            if role == "initial": state_name = "Initial"
            if role == "terminal": state_name = "Terminal"
            
            combined_sids = [e.sentence_id for e in b["extractions"]]
            combined_vars = []
            combined_events = []
            combined_guards = []
            entry_texts = []
            
            for e in b["extractions"]:
                combined_vars.extend(e.variables_mentioned)
                combined_events.extend(e.events_implied)
                combined_guards.extend(e.guards_implied)
                entry_texts.append(sent_map.get(e.sentence_id, ""))
                
            transitions = []
            if i < len(blocks) - 1:
                next_role = blocks[i+1]["role"]
                next_state_name = f"{next_role.title()}_{i+1}" if len(blocks) <= self.max_states else next_role.title()
                if next_role == "initial": next_state_name = "Initial"
                if next_role == "terminal": next_state_name = "Terminal"
                
                # Fetch first event of the *next* block to use as the transition trigger
                next_events = []
                for ne in blocks[i+1]["extractions"]:
                    next_events.extend(ne.events_implied)
                trans_event = next_events[0] if next_events else f"goto_{next_role.lower()}"
                
                transitions.append({
                    "from": state_name,
                    "to": next_state_name,
                    "event": trans_event
                })
                
            res = ExtractionResult(
                sentence_id=combined_sids[0] if combined_sids else "b0",
                states_mentioned=[state_name],
                transitions_implied=transitions,
                guards_implied=combined_guards,
                events_implied=list(set(combined_events)),
                variables_mentioned=list(set(combined_vars)),
                confidence=1.0,  # Synthesis confidence
                ambiguity_flags=[]
            )
            res.entry_action = "\n".join(entry_texts)
            abstracted.append(res)
            
        return abstracted
