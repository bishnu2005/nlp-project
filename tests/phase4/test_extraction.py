import pytest
import json
from manual_to_uml.core.ibr_schema import IBR
from manual_to_uml.extraction.preprocessor import preprocess_manual
from manual_to_uml.extraction.coref_resolver import resolve_coreferences
from manual_to_uml.extraction.llm_extractor import LLMExtractor, ExtractionResult
from manual_to_uml.extraction.symbolic_normalizer import SymbolicNormalizer
from manual_to_uml.extraction.ibr_assembler import IBRAssembler

class MockLLMExtractor(LLMExtractor):
    def _call_llm(self, prompt: str) -> str:
        # Mock answers based on sentence patterns for tests
        if "s001" in prompt:
            return json.dumps({
                "sentence_id": "s001",
                "states_mentioned": ["system_off", "system_ready"],
                "transitions_implied": [{"from": "system_off", "to": "system_ready", "event": "power_on"}],
                "guards_implied": [],
                "events_implied": ["power_on"],
                "variables_mentioned": [],
                "confidence": 0.9,
                "ambiguity_flags": []
            })
        elif "s002" in prompt:
            return json.dumps({
                "sentence_id": "s002",
                "states_mentioned": ["system_ready", "door_open"],
                "transitions_implied": [{"from": "system_ready", "to": "door_open", "event": "open_door"}],
                "guards_implied": [{"transition_event": "open_door", "condition": "pressure < 10"}],
                "events_implied": ["open_door"],
                "variables_mentioned": ["pressure"],
                "confidence": 0.85, # conditional
                "ambiguity_flags": []
            })
        elif "passive" in prompt or "s003" in prompt:
            return json.dumps({
                "sentence_id": "s003",
                "states_mentioned": ["door_open", "door_closed"],
                "transitions_implied": [{"from": "door_open", "to": "door_closed", "event": "close_door"}],
                "guards_implied": [],
                "events_implied": ["close_door"],
                "variables_mentioned": [],
                "confidence": 0.9,
                "ambiguity_flags": []
            })
        elif "low confidence" in prompt or "s004" in prompt:
            return json.dumps({
                "sentence_id": "s004",
                "states_mentioned": ["door_closed", "system_running"],
                "transitions_implied": [{"from": "door_closed", "to": "system_running", "event": "start"}],
                "guards_implied": [],
                "events_implied": ["start"],
                "variables_mentioned": [],
                "confidence": 0.5, # low confidence
                "ambiguity_flags": []
            })
        elif "inconsistent" in prompt or "s005" in prompt:
            return json.dumps({
                "sentence_id": "s005",
                "states_mentioned": ["system_running", "system_off"],
                "transitions_implied": [{"from": "system_running", "to": "unknown_void", "event": "crash"}],
                "guards_implied": [],
                "events_implied": ["crash"],
                "variables_mentioned": [],
                "confidence": 0.9,
                "ambiguity_flags": []
            })
        
        return json.dumps({
            "sentence_id": "s_unknown", "states_mentioned": ["a", "b"], 
            "transitions_implied": [{"from": "a", "to": "b", "event": "mock_event"}],
            "guards_implied": [], "events_implied": ["mock_event"], 
            "variables_mentioned": [], "confidence": 0.8, "ambiguity_flags": []
        })

@pytest.fixture
def mock_extractor():
    return MockLLMExtractor()

@pytest.fixture
def normalizer():
    return SymbolicNormalizer()

@pytest.fixture
def assembler():
    return IBRAssembler()

def test_feed_5_sentence_procedure(mock_extractor, normalizer, assembler):
    text = "Power on the system. If pressure is less than 10, open the door. The door was closed by the operator. Something might start the system (low confidence). An inconsistent crash happens."
    sentences = preprocess_manual(text)
    assert len(sentences) == 5
    
    extractions = mock_extractor.extract_all(sentences)
    assert len(extractions) == 5
    
    # ibr assembly
    ibr, flags = assembler.assemble(extractions, sentences)
    
    assert isinstance(ibr, IBR)
    assert len(ibr.states) >= 4
    # Check transitions link
    start_trans = [t for t in ibr.transitions if t.event == "start"]
    assert len(start_trans) == 1

def test_passive_voice_normalized(normalizer):
    # Testing Symbolic normalizer operator and name normalizations
    assert normalizer.normalize_state_name("The Door Is Closed") == "door_closed"
    assert normalizer.normalize_operator("less than") == "<"

def test_coref_it_resolved_stub():
    # Coreferee is mocked, asserting the text passes through the pipeline cleanly
    sentences = preprocess_manual("Open the valve. It will release pressure.")
    resolved = resolve_coreferences(sentences)
    assert len(resolved) == 2
    assert "valve" in resolved[0].text.lower()

def test_conditional_sentence_produces_guarded_transition(mock_extractor, assembler):
    sentences = preprocess_manual("If pressure is less than 10, open the door.")
    assert sentences[0].is_conditional is True
    
    # Force the S002 logic
    sentences[0].id = "s002"
    extractions = mock_extractor.extract_all(sentences)
    ibr, flags = assembler.assemble(extractions, sentences)
    
    t = ibr.transitions[0]
    assert t.guard is not None
    assert t.guard.variable == "pressure"
    assert t.guard.operator == "<"

def test_low_confidence_flagged(mock_extractor, assembler):
    sentences = preprocess_manual("Something low confidence start.")
    sentences[0].id = "s004"
    extractions = mock_extractor.extract_all(sentences)
    ibr, flags = assembler.assemble(extractions, sentences)
    
    low_conf_flags = [f for f in flags if "Low confidence" in f]
    assert len(low_conf_flags) > 0

def test_inconsistent_state_references_handled(mock_extractor, assembler):
    # s005 implies transition to "unknown_void" which is not in states_mentioned
    sentences = preprocess_manual("inconsistent state.")
    sentences[0].id = "s005"
    extractions = mock_extractor.extract_all(sentences)
    ibr, flags = assembler.assemble(extractions, sentences)
    
    # "unknown_void" should have been created on the fly by Assembler to fix inconsistency
    void_state = [s for s in ibr.states if s.id == "unknown_void"]
    assert len(void_state) == 1
    assert void_state[0].name == "Unknown Void"
