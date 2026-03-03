import pytest
from fastapi.testclient import TestClient

from manual_to_uml.extraction.preprocessor import preprocess_manual
from manual_to_uml.extraction.llm_extractor import LLMExtractor
from manual_to_uml.extraction.ibr_assembler import IBRAssembler
from manual_to_uml.verification.z3_verifier import verify_ibr
from manual_to_uml.verification.structural_verifier import check_structure
from manual_to_uml.simulation.simulator_api import app

# Create mock extractor for deterministic integration test since we can't guarantee API key
from tests.phase4.test_extraction import MockLLMExtractor

client = TestClient(app)

def test_full_pipeline_end_to_end():
    sample_manual = """
    Power on the system. If pressure is less than 10, open the door. 
    The door was closed by the operator.
    """
    
    # 1. Pipeline Extraction
    sentences = preprocess_manual(sample_manual)
    assert len(sentences) == 3
    
    # We use mock LLM here to ensure predictable test running without API keys
    extractor = MockLLMExtractor()
    extractions = extractor.extract_all(sentences)
    
    assembler = IBRAssembler()
    ibr, flags = assembler.assemble(extractions, sentences)
    
    assert ibr is not None
    assert len(ibr.states) > 0
    assert len(ibr.transitions) > 0
    
    # 2. Formal Verification
    # Our mock extractor produces valid structures that shouldn't fail fatally
    # Z3 check
    z3_issues = verify_ibr(ibr)
    assert isinstance(z3_issues, list)
    
    # Structural check
    structural_issues = check_structure(ibr)
    assert isinstance(structural_issues, list)
    
    # 3. Simulation & Chatbot
    # Load into API
    ibr_dict = ibr.model_dump()
    load_resp = client.post("/api/model/load", json=ibr_dict)
    assert load_resp.status_code == 200
    
    model_id = load_resp.json()["model_id"]
    initial_state = load_resp.json()["initial_state"]
    
    # Transition via Intent
    chat_resp = client.post("/api/chatbot/query", json={
        "model_id": model_id,
        "user_input": "start the system power on",
        "current_state": initial_state,
        "variable_values": {}
    })
    
    assert chat_resp.status_code == 200
    assert chat_resp.json()["transition_taken"] is True
    # mock_extractor returned "power_on" for s001 (system_off -> system_ready), 
    # which we expect to match
    assert chat_resp.json()["matched_event"] == "power_on"
