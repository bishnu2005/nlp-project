from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
import uuid
import logging

from manual_to_uml.core.ibr_schema import IBR, Transition, VariableType
from manual_to_uml.verification.z3_verifier import guard_to_z3
import z3

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Manual-to-UML Simulator API")

# CORS for frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount compile-manual router
from manual_to_uml.simulation.compile_endpoint import compile_router
app.include_router(compile_router)

# In-memory storage for loaded sessions
sessions_db: Dict[str, 'SimulatorSession'] = {}

class SimulatorSession:
    def __init__(self, session_id: str, ibr: IBR, initial_state: str):
        self.session_id = session_id
        self.ibr = ibr
        self.current_state = initial_state
        self.variable_values = {}
        for name, var in ibr.variables.items():
            if var.type == VariableType.INT: self.variable_values[name] = 0
            elif var.type == VariableType.FLOAT: self.variable_values[name] = 0.0
            elif var.type == VariableType.BOOLEAN: self.variable_values[name] = False
            else: self.variable_values[name] = ""
        self.history = []

    def get_valid_transitions(self) -> List[Transition]:
        valid = []
        possible = [t for t in self.ibr.transitions if t.from_state == self.current_state]
        for t in possible:
            if not t.guard or evaluate_guard_concrete(t.guard, self.ibr.variables, self.variable_values):
                valid.append(t)
        return valid

# Schema Definitions for API

class LoadModelResponse(BaseModel):
    model_id: str
    initial_state: str
    valid_actions: List[str]

class TransitionSummary(BaseModel):
    event: str
    target_state: str

class StateResponse(BaseModel):
    current_state: str
    valid_transitions: List[TransitionSummary]
    variable_values: Dict[str, Any]

class TransitionRequest(BaseModel):
    event: str
    variable_values: Dict[str, Any]

class TransitionResponse(BaseModel):
    success: bool
    new_state: str
    error: Optional[str] = None
    guard_evaluation: Dict[str, bool] = Field(default_factory=dict)

class TraceabilityResponse(BaseModel):
    source_sentences: List[str]

# Helper function to evaluate guard
def evaluate_guard_concrete(guard, variables_registry, variable_values) -> bool:
    if not guard:
        return True
        
    # Build a tiny Z3 evaluating wrapper for concrete values
    solver = z3.Solver()
    z3_vars = {}
    for name, var_def in variables_registry.items():
        if name in variable_values:
            val = variable_values[name]
            
            # Create Z3 Variable
            if var_def.type == VariableType.INT:
                z3_vars[name] = z3.Int(name)
                solver.add(z3_vars[name] == val)
            elif var_def.type == VariableType.FLOAT:
                z3_vars[name] = z3.Real(name)
                solver.add(z3_vars[name] == val)
            elif var_def.type == VariableType.BOOLEAN:
                z3_vars[name] = z3.Bool(name)
                solver.add(z3_vars[name] == val)
            elif var_def.type in (VariableType.STRING, VariableType.ENUM):
                z3_vars[name] = z3.String(name)
                solver.add(z3_vars[name] == z3.StringVal(val))
    
    # Missing variables context fallback (won't be in Z3 vars, guard_to_z3 will fail if not all are mapped)
    # So we ensure ALL variables in registry are defined
    for name, var_def in variables_registry.items():
         if name not in z3_vars:
            if var_def.type == VariableType.INT: z3_vars[name] = z3.Int(name)
            elif var_def.type == VariableType.FLOAT: z3_vars[name] = z3.Real(name)
            elif var_def.type == VariableType.BOOLEAN: z3_vars[name] = z3.Bool(name)
            elif var_def.type in (VariableType.STRING, VariableType.ENUM): z3_vars[name] = z3.String(name)

    try:
        expr = guard_to_z3(guard, variables_registry, z3_vars)
        solver.add(expr)
        result = solver.check()
        return result == z3.sat
    except Exception as e:
        logger.error(f"Error evaluating guard: {e}")
        return False

# Endpoints

@app.post("/api/model/load", response_model=LoadModelResponse)
def load_model(ibr: IBR):
    session_id = str(uuid.uuid4())
    
    # Find initial state
    initial_states = [s for s in ibr.states if s.is_initial]
    if not initial_states:
        raise HTTPException(status_code=400, detail="Invalid IBR: No initial state")
        
    initial_state = initial_states[0]
    
    session = SimulatorSession(session_id, ibr, initial_state.id)
    sessions_db[session_id] = session
    
    # Calculate initially valid actions
    valid_transitions = session.get_valid_transitions()
    valid_actions = list(set([t.event for t in valid_transitions]))
    
    logger.info(f"Loaded session {session_id} with initial state {initial_state.id}")
    return LoadModelResponse(
        model_id=session_id,  # Keep field name for frontend compatibility
        initial_state=initial_state.id,
        valid_actions=valid_actions
    )

@app.get("/api/model/{model_id}/state", response_model=StateResponse)
def get_model_state(model_id: str, current_state: Optional[str] = None):
    if model_id not in sessions_db:
        raise HTTPException(status_code=404, detail="Session not found")
        
    session = sessions_db[model_id]
    
    # Sync frontend state if provided (some frontend logic might override it)
    if current_state and current_state != session.current_state:
        state_exists = any(s.id == current_state for s in session.ibr.states)
        if not state_exists:
            raise HTTPException(status_code=404, detail=f"State '{current_state}' not found in model")
        session.current_state = current_state
        
    # Dynamically recompute valid transitions
    valid_trans = session.get_valid_transitions()
    valid_transitions_summary = [
        TransitionSummary(event=t.event, target_state=t.to_state)
        for t in valid_trans
    ]
    
    return StateResponse(
        current_state=session.current_state,
        valid_transitions=valid_transitions_summary,
        variable_values=session.variable_values
    )

@app.post("/api/model/{model_id}/transition", response_model=TransitionResponse)
def compute_transition(model_id: str, current_state: str, request: TransitionRequest):
    if model_id not in sessions_db:
        raise HTTPException(status_code=404, detail="Session not found")
        
    session = sessions_db[model_id]
    
    # Update session variables from request
    session.variable_values.update(request.variable_values)
    session.current_state = current_state
    
    # Recompute valid transitions dynamically
    valid_trans = session.get_valid_transitions()
    
    # Filter to requested event
    matching_trans = [t for t in valid_trans if t.event == request.event]
    
    if not matching_trans:
        # It's invalid. Determine if it's due to guard failure or just completely invalid event.
        possible_all = [t for t in session.ibr.transitions if t.from_state == current_state and t.event == request.event]
        if not possible_all:
            raise HTTPException(status_code=409, detail=f"Event '{request.event}' is not valid from state '{current_state}'")
        else:
            raise HTTPException(
                 status_code=409, 
                 detail={
                     "message": "Transition rejected: Guards failed.",
                     "guard_evaluation": {t.id: False for t in possible_all}
                 }
            )
        
    selected_transition = matching_trans[0]
    
    # Apply transition state change immediately
    session.current_state = selected_transition.to_state
    session.history.append((current_state, request.event, session.current_state))
    
    return TransitionResponse(
        success=True,
        new_state=session.current_state,
        guard_evaluation={selected_transition.id: True}
    )

@app.get("/api/model/{model_id}/traceability/{state_id}", response_model=TraceabilityResponse)
def get_traceability(model_id: str, state_id: str):
    if model_id not in sessions_db:
        raise HTTPException(status_code=404, detail="Session not found")
        
    session = sessions_db[model_id]
    ibr = session.ibr
    
    state = next((s for s in ibr.states if s.id == state_id), None)
    if not state:
        raise HTTPException(status_code=404, detail=f"State '{state_id}' not found")
        
    sentences = []
    for sid in state.source_sentence_ids:
        if sid in ibr.source_sentences:
            sentences.append(f"[{sid}] {ibr.source_sentences[sid]}")
            
    return TraceabilityResponse(source_sentences=sentences)

class ChatbotQueryRequest(BaseModel):
    model_id: str
    user_input: str
    current_state: str
    variable_values: Dict[str, Any]

class ChatbotQueryResponse(BaseModel):
    response_text: str
    confidence: float
    matched_event: Optional[str] = None
    transition_taken: Optional[bool] = False
    new_state: Optional[str] = None
    clarification_needed: bool = False
    clarification_options: Optional[List[str]] = None

@app.post("/api/chatbot/query", response_model=ChatbotQueryResponse)
def chatbot_query(request: ChatbotQueryRequest):
    if request.model_id not in sessions_db:
        raise HTTPException(status_code=404, detail="Session not found")
        
    session = sessions_db[request.model_id]
    ibr = session.ibr
    
    # Verify state
    if not any(s.id == request.current_state for s in ibr.states):
        raise HTTPException(status_code=400, detail="Invalid current state")
        
    # Lazy load here to avoid circular imports / missing deps at startup if partial test
    from manual_to_uml.chatbot.intent_mapper import map_intent, CONFIDENCE_THRESHOLD
    from manual_to_uml.chatbot.response_resolver import resolve_response
    
    try:
        intent = map_intent(request.user_input, ibr, request.current_state)
        
        if intent.confidence < CONFIDENCE_THRESHOLD:
            clarifications = [x[0] for x in intent.alternatives] if intent.alternatives else []
            resp_text = resolve_response(intent, ibr, request.current_state, request.variable_values)
            return ChatbotQueryResponse(
                response_text=resp_text,
                confidence=intent.confidence,
                clarification_needed=True,
                clarification_options=clarifications
            )
            
        # Resolved
        resp_text = resolve_response(intent, ibr, request.current_state, request.variable_values)
        
        # Did it actually transition? Check if it was rejected by guards
        transitioned = False
        new_state = None
        if "action" in resp_text.lower() and "blocked" not in resp_text.lower() and "not valid" not in resp_text.lower():
            # If it passed guards and validity criteria, resolve_response constructs a success string
            transitioned = True
            # Let's cleanly grab the new_state id
            possible_transitions = [t for t in ibr.transitions if t.from_state == request.current_state and t.event == intent.matched_event]
            for t in possible_transitions:
                # We know at least one passed from resolve_response logic
                # For exact 1-1 mappings we just grab the first valid
                if t.guard:
                    from manual_to_uml.simulation.simulator_api import evaluate_guard_concrete
                    if evaluate_guard_concrete(t.guard, ibr.variables, request.variable_values):
                        new_state = t.to_state
                        break
                else:
                    new_state = t.to_state
                    break
        
        return ChatbotQueryResponse(
            response_text=resp_text,
            confidence=intent.confidence,
            matched_event=intent.matched_event,
            transition_taken=transitioned,
            new_state=new_state
        )

    except Exception as e:
        logger.error(f"Chatbot query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
