from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from manual_to_uml.core.ibr_schema import IBR

class DiffItem(BaseModel):
    change_type: str  # ADDED / REMOVED / MODIFIED
    element_type: str  # STATE / TRANSITION / GUARD / VARIABLE
    element_id: str
    old_value: Optional[Dict[str, Any]] = None
    new_value: Optional[Dict[str, Any]] = None

def diff_ibr(ibr_v1: IBR, ibr_v2: IBR) -> List[DiffItem]:
    diffs = []
    
    # Compare States (by ID)
    states_v1 = {s.id: s for s in ibr_v1.states}
    states_v2 = {s.id: s for s in ibr_v2.states}
    
    for sid, s1 in states_v1.items():
        if sid not in states_v2:
            diffs.append(DiffItem(change_type="REMOVED", element_type="STATE", element_id=sid, old_value=s1.model_dump()))
        else:
            s2 = states_v2[sid]
            # Consider modified if names or attributes change, though the rules mainly specified just detecting added/removed.
            # We will perform a simple deep compare on the serialized dict for MODIFIED detection across the board if needed.
            if s1.model_dump() != s2.model_dump():
                 diffs.append(DiffItem(change_type="MODIFIED", element_type="STATE", element_id=sid, 
                                       old_value=s1.model_dump(), new_value=s2.model_dump()))

    for sid, s2 in states_v2.items():
        if sid not in states_v1:
            diffs.append(DiffItem(change_type="ADDED", element_type="STATE", element_id=sid, new_value=s2.model_dump()))
            
    # Compare Transitions (by from_state + event as per requirements, or ID? 
    # Requirement: "Match states by ID, transitions by from+event")
    def trans_key(t): return f"{t.from_state}::{t.event}"
    
    trans_v1 = {trans_key(t): t for t in ibr_v1.transitions}
    trans_v2 = {trans_key(t): t for t in ibr_v2.transitions}
    
    for tkey, t1 in trans_v1.items():
        if tkey not in trans_v2:
            diffs.append(DiffItem(change_type="REMOVED", element_type="TRANSITION", element_id=t1.id, old_value=t1.model_dump()))
        else:
            t2 = trans_v2[tkey]
            # Detect modified guards
            g1_dump = t1.guard.model_dump() if t1.guard else None
            g2_dump = t2.guard.model_dump() if t2.guard else None
            
            if g1_dump != g2_dump:
                diffs.append(DiffItem(change_type="MODIFIED", element_type="GUARD", element_id=t2.id, 
                                      old_value=g1_dump, new_value=g2_dump))
            elif t1.model_dump(exclude={'guard'}) != t2.model_dump(exclude={'guard'}):
                # Transition modified in some other way (e.g. action or to_state changed)
                diffs.append(DiffItem(change_type="MODIFIED", element_type="TRANSITION", element_id=t2.id,
                                      old_value=t1.model_dump(), new_value=t2.model_dump()))

    for tkey, t2 in trans_v2.items():
        if tkey not in trans_v1:
            diffs.append(DiffItem(change_type="ADDED", element_type="TRANSITION", element_id=t2.id, new_value=t2.model_dump()))
            
    # Compare Variables
    vars_v1 = ibr_v1.variables
    vars_v2 = ibr_v2.variables
    
    for vname, v1 in vars_v1.items():
        if vname not in vars_v2:
            diffs.append(DiffItem(change_type="REMOVED", element_type="VARIABLE", element_id=vname, old_value=v1.model_dump()))
        else:
            v2 = vars_v2[vname]
            if v1.model_dump() != v2.model_dump():
                diffs.append(DiffItem(change_type="MODIFIED", element_type="VARIABLE", element_id=vname,
                                      old_value=v1.model_dump(), new_value=v2.model_dump()))

    for vname, v2 in vars_v2.items():
        if vname not in vars_v1:
            diffs.append(DiffItem(change_type="ADDED", element_type="VARIABLE", element_id=vname, new_value=v2.model_dump()))

    return diffs
