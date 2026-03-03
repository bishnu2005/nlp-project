import pytest
from fastapi.testclient import TestClient
from manual_to_uml.core.ibr_schema import IBR, State, Transition, GuardNode, GuardNodeType, Variable, VariableType
from manual_to_uml.simulation.simulator_api import app

client = TestClient(app)

@pytest.fixture
def valid_ibr_data():
    return {
        "version": "1.0",
        "manual_id": "m1",
        "states": [
            {"id": "s1", "name": "Start", "is_initial": True, "source_sentence_ids": ["sent1"]},
            {"id": "s2", "name": "Running"}
        ],
        "transitions": [
            {
                "id": "t1", "from_state": "s1", "to_state": "s2", "event": "start",
                "guard": {
                    "node_type": "condition", "variable": "temp", "operator": ">", "literal_value": 50.0
                }
            }
        ],
        "variables": {
            "temp": {"name": "temp", "type": "float"}
        },
        "source_sentences": {
            "sent1": "The system begins here."
        }
    }

def test_load_valid_ibr(valid_ibr_data):
    response = client.post("/api/model/load", json=valid_ibr_data)
    assert response.status_code == 200
    data = response.json()
    assert "model_id" in data
    assert data["initial_state"] == "s1"
    assert "start" in data["valid_actions"]

def test_load_invalid_ibr():
    invalid_data = {"version": "1.0", "manual_id": "m1", "states": [], "transitions": [], "variables": {}, "source_sentences": {}}
    response = client.post("/api/model/load", json=invalid_data)
    assert response.status_code == 422 # Pydantic validation error

def test_valid_transition(valid_ibr_data):
    # Load model
    load_resp = client.post("/api/model/load", json=valid_ibr_data)
    model_id = load_resp.json()["model_id"]
    
    # Post transition that satisfies guard
    trans_resp = client.post(f"/api/model/{model_id}/transition?current_state=s1", json={
        "event": "start",
        "variable_values": {"temp": 60.0}
    })
    
    assert trans_resp.status_code == 200
    data = trans_resp.json()
    assert data["success"] is True
    assert data["new_state"] == "s2"
    assert data["guard_evaluation"]["t1"] is True

def test_invalid_transition_not_in_model(valid_ibr_data):
    load_resp = client.post("/api/model/load", json=valid_ibr_data)
    model_id = load_resp.json()["model_id"]
    
    trans_resp = client.post(f"/api/model/{model_id}/transition?current_state=s1", json={
        "event": "unknown_event",
        "variable_values": {}
    })
    
    assert trans_resp.status_code == 409
    assert "not valid" in trans_resp.json()["detail"]

def test_transition_with_failed_guard(valid_ibr_data):
    load_resp = client.post("/api/model/load", json=valid_ibr_data)
    model_id = load_resp.json()["model_id"]
    
    trans_resp = client.post(f"/api/model/{model_id}/transition?current_state=s1", json={
        "event": "start",
        "variable_values": {"temp": 40.0} # Guard temp > 50 will fail
    })
    
    assert trans_resp.status_code == 409
    data = trans_resp.json()["detail"]
    assert "guard_evaluation" in data
    assert data["guard_evaluation"]["t1"] is False

def test_traceability_query(valid_ibr_data):
    load_resp = client.post("/api/model/load", json=valid_ibr_data)
    model_id = load_resp.json()["model_id"]
    
    trace_resp = client.get(f"/api/model/{model_id}/traceability/s1")
    assert trace_resp.status_code == 200
    data = trace_resp.json()
    assert len(data["source_sentences"]) == 1
    assert "The system begins here" in data["source_sentences"][0]
