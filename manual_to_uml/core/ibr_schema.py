from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, model_validator, Field

class VariableType(str, Enum):
    FLOAT = "float"
    INT = "int"
    STRING = "string"
    BOOLEAN = "boolean"
    ENUM = "enum"

class Variable(BaseModel):
    name: str
    type: VariableType
    enum_values: Optional[List[str]] = None
    unit: Optional[str] = None

class GuardNodeType(str, Enum):
    CONDITION = "condition"
    AND = "AND"
    OR = "OR"
    NOT = "NOT"

class GuardNode(BaseModel):
    # Recursive model for Guard DSL AST
    node_type: GuardNodeType
    variable: Optional[str] = None
    operator: Optional[str] = None
    literal_value: Optional[Any] = None
    
    left: Optional['GuardNode'] = None
    right: Optional['GuardNode'] = None
    operand: Optional['GuardNode'] = None

    def get_all_conditions(self) -> List['GuardNode']:
        if self.node_type == GuardNodeType.CONDITION:
            return [self]
        conditions = []
        if self.left:
            conditions.extend(self.left.get_all_conditions())
        if self.right:
            conditions.extend(self.right.get_all_conditions())
        if self.operand:
            conditions.extend(self.operand.get_all_conditions())
        return conditions

class Transition(BaseModel):
    id: str
    from_state: str
    to_state: str
    event: str
    guard: Optional[GuardNode] = None
    action: Optional[str] = None
    source_sentence_ids: List[str] = Field(default_factory=list)

class State(BaseModel):
    id: str
    name: str
    is_initial: bool = False
    is_terminal: bool = False
    entry_action: Optional[str] = None
    exit_action: Optional[str] = None
    invariant: Optional[GuardNode] = None
    source_sentence_ids: List[str] = Field(default_factory=list)

class IBR(BaseModel):
    version: str
    manual_id: str
    states: List[State]
    transitions: List[Transition]
    variables: Dict[str, Variable]
    source_sentences: Dict[str, str]

    @model_validator(mode='after')
    def validate_ibr(self) -> 'IBR':
        if not self.states:
            raise ValueError("IBR must have at least one state")
        
        initial_states = [s for s in self.states if s.is_initial]
        if not initial_states:
            raise ValueError("IBR must have at least one initial state")
            
        state_ids = [s.id for s in self.states]
        if len(state_ids) != len(set(state_ids)):
            raise ValueError("State IDs must be unique")
            
        # Validate Guard variables and types
        for t in self.transitions:
            if t.guard:
                self._validate_guard(t.guard)
                
        for s in self.states:
            if s.invariant:
                self._validate_guard(s.invariant)
                
        return self
        
    def _validate_guard(self, guard: GuardNode):
        for cond in guard.get_all_conditions():
            if cond.variable not in self.variables:
                raise ValueError(f"Variable '{cond.variable}' in guard not found in registry")
            var_def = self.variables[cond.variable]
            
            # Type mismatch logic
            if var_def.type == VariableType.INT and not isinstance(cond.literal_value, int):
                if isinstance(cond.literal_value, float) and cond.literal_value.is_integer():
                    pass # treat 1.0 as 1
                else:
                    raise ValueError(f"Type mismatch: '{cond.variable}' is INT, got {type(cond.literal_value)}")
            elif var_def.type == VariableType.FLOAT and not isinstance(cond.literal_value, (float, int)):
                raise ValueError(f"Type mismatch: '{cond.variable}' is FLOAT, got {type(cond.literal_value)}")
            elif var_def.type == VariableType.STRING and not isinstance(cond.literal_value, str):
                raise ValueError(f"Type mismatch: '{cond.variable}' is STRING, got {type(cond.literal_value)}")
            elif var_def.type == VariableType.BOOLEAN and not isinstance(cond.literal_value, bool):
                raise ValueError(f"Type mismatch: '{cond.variable}' is BOOLEAN, got {type(cond.literal_value)}")
            elif var_def.type == VariableType.ENUM:
                if not isinstance(cond.literal_value, str):
                    raise ValueError(f"Type mismatch: '{cond.variable}' is ENUM, got {type(cond.literal_value)}")
                if var_def.enum_values and cond.literal_value not in var_def.enum_values:
                    raise ValueError(f"Enum value '{cond.literal_value}' for '{cond.variable}' not in allowed values: {var_def.enum_values}")
