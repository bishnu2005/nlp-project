import pytest
from manual_to_uml.extraction.guard_parser import GuardParser

def test_guard_parser_simple_condition():
    parser = GuardParser()
    ast = parser.parse("pressure > 5")
    
    assert ast is not None
    assert ast["node_type"] == "condition"
    assert ast["variable"] == "pressure"
    assert ast["operator"] == ">"
    assert ast["literal_value"] == 5
    assert ast["left"] is None
    assert ast["right"] is None

def test_guard_parser_logical_and():
    parser = GuardParser()
    ast = parser.parse("pressure > 5 AND temp < 60")
    
    assert ast is not None
    assert ast["node_type"] == "AND"
    
    assert ast["left"] is not None
    assert ast["left"]["node_type"] == "condition"
    assert ast["left"]["variable"] == "pressure"
    assert ast["left"]["operator"] == ">"
    assert ast["left"]["literal_value"] == 5
    
    assert ast["right"] is not None
    assert ast["right"]["node_type"] == "condition"
    assert ast["right"]["variable"] == "temp"
    assert ast["right"]["operator"] == "<"
    assert ast["right"]["literal_value"] == 60

def test_guard_parser_boolean_variable():
    parser = GuardParser()
    ast = parser.parse("leak_detected")
    
    assert ast is not None
    assert ast["node_type"] == "condition"
    assert ast["variable"] == "leak_detected"
    assert ast["operator"] == "=="
    assert ast["literal_value"] is True
