import logging
from typing import List, Dict, Optional
from manual_to_uml.extraction.llm_extractor import ExtractionResult
from manual_to_uml.extraction.preprocessor import Sentence

logger = logging.getLogger(__name__)

class StateAbstractor:
    def __init__(self):
        self.roles = [
            "initial", "pre_start_inspection", "ready", "starting", "running",
            "high_pressure", "high_temperature", "leak_detected", "abnormal_vibration",
            "emergency_shutdown", "shutting_down", "terminal"
        ]
        self.max_states = 15
        
        self.max_states = 15



    def _merge_blocks(self, blocks: List[Dict]) -> List[Dict]:
        """Merge blocks sequentially to obey budget."""
        # Simple frequency compression: group identical non-consecutive roles if over budget
        merged = []
        for role in self.roles + ["conditional"]:
            combined = {"role": role, "primitives": []}
            for b in blocks:
                if b["role"] == role:
                    combined["primitives"].extend(b["primitives"])
            if combined["primitives"]:
                merged.append(combined)
        return merged

    def abstract(self, primitives: List['ProcedurePrimitive'], sentences: List[Sentence]) -> List[ExtractionResult]:
        from manual_to_uml.extraction.llm_extractor import ExtractionResult
        sent_map = {s.id: s.text for s in sentences}
        sent_idx_map = {s.id: idx for idx, s in enumerate(sentences)}
        
        # 1. Classify & Group consecutive primitives with the same role
        blocks = []
        current_block = []
        current_role = None
        
        for prim in primitives:
            role = prim.role_hint if prim.role_hint else "running"
            
            # If role is conditional, append to current_block. Conditions do not force state breaks.
            if role == "conditional":
                if current_block:
                    current_block.append(prim)
                else:
                    current_block = [prim]
                    current_role = role
                continue
            
            # If role is a fault, it forces a new block
            if role == current_role and not role.startswith("fault_"):
                current_block.append(prim)
            else:
                if current_block:
                    blocks.append({"role": current_role, "primitives": current_block})
                current_block = [prim]
                current_role = role
                
        if current_block:
            blocks.append({"role": current_role, "primitives": current_block})
            
        # Fallback if no primitives passed through
        if not blocks:
            logger.warning("Abstraction yielded 0 blocks. Creating a fallback Initial state to satisfy IBR schema.")
            fallback_res = ExtractionResult(
                sentence_id=sentences[0].id if sentences else "s000",
                states_mentioned=["Initial"],
                confidence=1.0
            )
            return [fallback_res]
            
        # 2. State Budget Limiter
        if len(blocks) > self.max_states:
             logger.info(f"State budget exceeded ({len(blocks)}). Merging based on role to {len(self.roles)} states max.")
             blocks = self._merge_blocks(blocks)
             
        # 3. Build Abstract Extractions (1 per Block)
        abstracted = []
        
        # Pre-assign state names
        for i, b in enumerate(blocks):
            role = b["role"]
            state_name = role.replace("fault_", "").replace("_", " ").title()
            
            if not role.startswith("fault_") and len(blocks) > self.max_states:
                state_name = role.replace("_", " ").title()
            elif not role.startswith("fault_"):
                 state_name = f"{role.replace('_', ' ').title()} {i+1}"
                 
            if i == 0 and not role.startswith("fault_"): state_name = "Initial"
            elif i == len(blocks) - 1 and not role.startswith("fault_"): state_name = "Terminal"
            
            b["state_name"] = state_name
            combined_sids = []
            for p in b["primitives"]:
                combined_sids.extend([f"s{sid:03d}" for sid in p.source_sentence_ids])
            b["min_idx"] = min([sent_idx_map.get(sid, 999999) for sid in combined_sids]) if combined_sids else 999999

        op_blocks = [b for b in blocks if not b["role"].startswith("fault_") and b["role"] != "conditional"]
        
        for i, b in enumerate(blocks):
            role = b["role"]
            state_name = b["state_name"]
            is_fault = role.startswith("fault_")
            is_cond = role == "conditional"
            
            combined_sids = []
            combined_events = []
            combined_guards = []
            entry_texts = []
            
            for p in b["primitives"]:
                sids = [f"s{sid:03d}" for sid in p.source_sentence_ids]
                combined_sids.extend(sids)
                if p.event:
                    combined_events.append(p.event)
                if p.guard:
                    g_copy = dict(p.guard)
                    if "transition_event" not in g_copy and p.event:
                        g_copy["transition_event"] = p.event
                    elif "transition_event" not in g_copy and combined_events:
                        g_copy["transition_event"] = combined_events[-1]
                    combined_guards.append(g_copy)
                for sid in sids:
                    txt = sent_map.get(sid, "")
                    if txt and txt not in entry_texts:
                        entry_texts.append(txt)
                        
            transitions = []
            
            if is_fault or is_cond:
                nearest_op = None
                min_dist = 999999
                for ob in op_blocks:
                    if ob["min_idx"] <= b["min_idx"]:
                        dist = b["min_idx"] - ob["min_idx"]
                        if dist < min_dist:
                            min_dist = dist
                            nearest_op = ob
                from_state = nearest_op["state_name"] if nearest_op else (op_blocks[0]["state_name"] if op_blocks else "Initial")
                
                my_events = combined_events
                trans_event = my_events[0] if my_events else f"goto_{state_name.replace(' ', '_').lower()}"
                
                # If just conditional rule block, map conditional back to nearest operational node transitions.
                if is_cond:
                    state_name = from_state
                else:    
                    transitions.append({
                        "from": from_state,
                        "to": state_name,
                        "event": trans_event
                    })
            else:
                op_idx = op_blocks.index(b)
                if op_idx > 0:
                    from_state = op_blocks[op_idx - 1]["state_name"]
                    my_events = combined_events
                    trans_event = my_events[0] if my_events else f"goto_{role.lower()}"
                    
                    transitions.append({
                        "from": from_state,
                        "to": state_name,
                        "event": trans_event
                    })
                
            res = ExtractionResult(
                sentence_id=combined_sids[0] if combined_sids else "s000",
                states_mentioned=[state_name],
                transitions_implied=transitions,
                guards_implied=combined_guards,
                events_implied=list(set(combined_events)),
                variables_mentioned=[], # Extracted auto via ibrAssembler parsing
                confidence=1.0,
                ambiguity_flags=[],
                source_sentence_ids=list(set(combined_sids))
            )
            res.entry_action = "\n".join(entry_texts)
            abstracted.append(res)
            
        from manual_to_uml.config import DEBUG_PIPELINE
        if DEBUG_PIPELINE:
            logger.info("[DEBUG] Generated states")
            for s in abstracted:
                logger.info({
                    "id": s.states_mentioned[0] if s.states_mentioned else "",
                    "name": s.states_mentioned[0] if s.states_mentioned else "",
                    "role": "extracted_state",
                    "sentences": s.source_sentence_ids
                })
                
        return abstracted
