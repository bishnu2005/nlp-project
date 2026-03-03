import z3
from typing import Dict, List
from manual_to_uml.core.ibr_schema import (
    IBR, GuardNode, GuardNodeType, Variable, VariableType
)
from pydantic import BaseModel
from enum import Enum

class ConflictType(str, Enum):
    OVERLAP = "OVERLAP"
    UNSATISFIABLE = "UNSATISFIABLE"
    ALWAYS_TRUE = "ALWAYS_TRUE"
    MISSING_ELSE = "MISSING_ELSE"
    CONTRADICTORY_INVARIANT = "CONTRADICTORY_INVARIANT"

class GuardConflict(BaseModel):
    conflict_type: ConflictType
    severity: str  # "ERROR" or "WARNING"
    transition_ids: List[str]
    description: str
    source_sentence_ids: List[str]

def guard_to_z3(guard: GuardNode, registry: Dict[str, Variable], z3_vars: Dict[str, z3.ExprRef]) -> z3.ExprRef:
    if guard.node_type == GuardNodeType.CONDITION:
        z3_var = z3_vars[guard.variable]
        val = guard.literal_value
        op = guard.operator
        
        if isinstance(val, bool):
            z3_val = z3.BoolVal(val)
        elif isinstance(val, int):
            z3_val = z3.IntVal(val)
        elif isinstance(val, float):
            z3_val = z3.RealVal(val)
        elif isinstance(val, str):
            z3_val = z3.StringVal(val)
        else:
            raise ValueError(f"Unsupported Z3 value type for {val}")
            
        if op == "==": return z3_var == z3_val
        if op == "!=": return z3_var != z3_val
        if op == ">": return z3_var > z3_val
        if op == ">=": return z3_var >= z3_val
        if op == "<": return z3_var < z3_val
        if op == "<=": return z3_var <= z3_val
        raise ValueError(f"Unknown operator: {op}")
        
    elif guard.node_type == GuardNodeType.AND:
        return z3.And(guard_to_z3(guard.left, registry, z3_vars), guard_to_z3(guard.right, registry, z3_vars))
    elif guard.node_type == GuardNodeType.OR:
        return z3.Or(guard_to_z3(guard.left, registry, z3_vars), guard_to_z3(guard.right, registry, z3_vars))
    elif guard.node_type == GuardNodeType.NOT:
        return z3.Not(guard_to_z3(guard.operand, registry, z3_vars))
    
    raise ValueError(f"Unknown guard node type: {guard.node_type}")

def verify_ibr(ibr: IBR) -> List[GuardConflict]:
    conflicts: List[GuardConflict] = []
    
    # 1. Setup Z3 variables
    z3_vars = {}
    for name, var in ibr.variables.items():
        if var.type == VariableType.INT:
            z3_vars[name] = z3.Int(name)
        elif var.type == VariableType.FLOAT:
            z3_vars[name] = z3.Real(name)
        elif var.type == VariableType.BOOLEAN:
            z3_vars[name] = z3.Bool(name)
        elif var.type in (VariableType.STRING, VariableType.ENUM):
            z3_vars[name] = z3.String(name)
            
    # Helper to check SAT
    def is_sat(expr) -> bool:
        solver = z3.Solver()
        solver.add(expr)
        return solver.check() == z3.sat
        
    def is_unsat(expr) -> bool:
        solver = z3.Solver()
        solver.add(expr)
        return solver.check() == z3.unsat

    for t in ibr.transitions:
        if not t.guard: continue
        z3_g = guard_to_z3(t.guard, ibr.variables, z3_vars)
        
        # unsatisfiable
        if is_unsat(z3_g):
            conflicts.append(GuardConflict(
                conflict_type=ConflictType.UNSATISFIABLE,
                severity="ERROR",
                transition_ids=[t.id],
                description=f"Guard for transition {t.id} can never be true",
                source_sentence_ids=t.source_sentence_ids
            ))
            
        # always true
        if is_unsat(z3.Not(z3_g)):
            conflicts.append(GuardConflict(
                conflict_type=ConflictType.ALWAYS_TRUE,
                severity="WARNING",
                transition_ids=[t.id],
                description=f"Guard for transition {t.id} is always true",
                source_sentence_ids=t.source_sentence_ids
            ))

    # Group transitions by (from_state, event)
    grouped = {}
    for t in ibr.transitions:
        if not t.guard: continue
        key = (t.from_state, t.event)
        if key not in grouped: grouped[key] = []
        grouped[key].append(t)
        
    for key, transitions in grouped.items():
        if len(transitions) < 2: continue
        
        for i in range(len(transitions)):
            for j in range(i + 1, len(transitions)):
                t1 = transitions[i]
                t2 = transitions[j]
                
                z3_g1 = guard_to_z3(t1.guard, ibr.variables, z3_vars)
                z3_g2 = guard_to_z3(t2.guard, ibr.variables, z3_vars)
                
                if is_sat(z3.And(z3_g1, z3_g2)):
                    conflicts.append(GuardConflict(
                        conflict_type=ConflictType.OVERLAP,
                        severity="ERROR",
                        transition_ids=[t1.id, t2.id],
                        description=f"Guards for transitions {t1.id} and {t2.id} overlap",
                        source_sentence_ids=t1.source_sentence_ids + t2.source_sentence_ids
                    ))
                    
        # Check missing else
        z3_guards = [guard_to_z3(t.guard, ibr.variables, z3_vars) for t in transitions]
        combined_or = z3.Or(*z3_guards)
        if is_sat(z3.Not(combined_or)):
             conflicts.append(GuardConflict(
                conflict_type=ConflictType.MISSING_ELSE,
                severity="WARNING",
                transition_ids=[t.id for t in transitions],
                description=f"Guards for event '{key[1]}' from state '{key[0]}' do not cover all possible inputs",
                source_sentence_ids=[]
            ))
            
    return conflicts
