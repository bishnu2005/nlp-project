from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

class PrimitiveType(str, Enum):
    ACTION = "action"
    CONDITIONAL = "conditional"
    FAULT = "fault"
    SHUTDOWN = "shutdown"
    INSPECTION = "inspection"

class ProcedurePrimitive(BaseModel):
    type: PrimitiveType
    event: Optional[str] = None
    guard: Optional[Dict[str, Any]] = None
    action: Optional[str] = None
    role_hint: Optional[str] = None
    source_sentence_ids: List[int] = []
