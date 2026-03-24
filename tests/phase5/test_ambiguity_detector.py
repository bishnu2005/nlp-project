import pytest
from manual_to_uml.extraction.preprocessor import Sentence
from manual_to_uml.verification.ambiguity_detector import AmbiguityDetector, AmbiguityType

@pytest.fixture
def detector():
    return AmbiguityDetector(api_key=None) # Using mock for tests

def create_sentence(id="s1", text="text", is_conditional=False):
    return Sentence(id=id, text=text, original_index=0, is_conditional=is_conditional)

def test_vague_quantifier(detector):
    sent = create_sentence(text="Wait until the system is stable")
    flags = detector.detect([sent])
    
    assert len(flags) == 1
    assert flags[0]["ambiguity_type"] == AmbiguityType.VAGUE_QUANTIFIER

def test_implicit_branching(detector):
    sent = create_sentence(text="Otherwise, proceed to step 4")
    flags = detector.detect([sent])
    
    assert len(flags) == 1
    assert flags[0]["ambiguity_type"] == AmbiguityType.IMPLICIT_BRANCHING

def test_unambiguous_sentence(detector):
    sent = create_sentence(text="Turn the valve to the open position.")
    flags = detector.detect([sent])
    
    assert len(flags) == 0

def test_llm_multiple_parse(detector):
    sent = create_sentence(text="This has a mock_multiple parse requirement.")
    flags = detector.detect([sent])
    
    assert len(flags) == 1
    assert flags[0]["ambiguity_type"] == AmbiguityType.MULTIPLE_PARSE
    assert len(flags[0]["interpretations"]) > 1

def test_deduplication(detector):
    # This sentence has both vague quantifier and mock multiple. Both should be returned as they are different types.
    # Deduplication in detector only applies if it's the exact same type to avoid double counting
    sent = create_sentence(text="Wait until stable mock_multiple")
    flags = detector.detect([sent])
    
    assert len(flags) == 2
    types = [f["ambiguity_type"] for f in flags]
    assert AmbiguityType.VAGUE_QUANTIFIER in types
    assert AmbiguityType.MULTIPLE_PARSE in types
