import logging
from typing import List, Dict, Any
from manual_to_uml.ir.procedure_ir import ProcedurePrimitive, PrimitiveType
from manual_to_uml.extraction.state_mapper import get_mapped_state

logger = logging.getLogger(__name__)

def build_ir(events: List[str], conditions: List[str], sentence_ids: List[int]) -> List[ProcedurePrimitive]:
    primitives = []
    
    for event in events:
        role_hint = get_mapped_state(event)
        
        p_type = PrimitiveType.ACTION
        if "fault_" in role_hint:
            p_type = PrimitiveType.FAULT
        elif role_hint == "shutting_down":
            p_type = PrimitiveType.SHUTDOWN
        elif role_hint == "inspection":
            p_type = PrimitiveType.INSPECTION

        prim = ProcedurePrimitive(
            type=p_type,
            event=event,
            action=event,
            role_hint=role_hint,
            source_sentence_ids=sentence_ids
        )
        primitives.append(prim)
        
    for cond in conditions:
        prim = ProcedurePrimitive(
            type=PrimitiveType.CONDITIONAL,
            guard={"condition": cond},
            role_hint="conditional",
            source_sentence_ids=sentence_ids
        )
        primitives.append(prim)
    from manual_to_uml.config import DEBUG_PIPELINE
    if DEBUG_PIPELINE:
        logger.info("[DEBUG] IR primitives")
        for p in primitives:
            logger.info({
                "type": p.type,
                "event": p.event,
                "guard": p.guard,
                "source_sentence_ids": p.source_sentence_ids
            })
            
    return primitives
