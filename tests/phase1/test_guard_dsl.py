import pytest
from manual_to_uml.core.ibr_schema import Variable, VariableType, GuardNodeType
from manual_to_uml.core.guard_dsl import parse_guard
from manual_to_uml.core.exceptions import ParseError

@pytest.fixture
def registry():
    return {
        "temperature": Variable(name="temperature", type=VariableType.FLOAT),
        "pressure": Variable(name="pressure", type=VariableType.FLOAT),
        "status": Variable(name="status", type=VariableType.STRING),
        "enabled": Variable(name="enabled", type=VariableType.BOOLEAN),
        "a": Variable(name="a", type=VariableType.INT),
        "b": Variable(name="b", type=VariableType.INT),
        "c": Variable(name="c", type=VariableType.STRING),
    }

def test_simple_condition(registry):
    node = parse_guard("temperature > 50", registry)
    assert node.node_type == GuardNodeType.CONDITION
    assert node.variable == "temperature"
    assert node.operator == ">"
    assert node.literal_value == 50

def test_and_condition(registry):
    node = parse_guard("temperature > 50 AND pressure < 3.0", registry)
    assert node.node_type == GuardNodeType.AND
    assert node.left.variable == "temperature"
    assert node.right.variable == "pressure"
    assert node.right.literal_value == 3.0

def test_not_condition(registry):
    node = parse_guard("NOT (status == 'running')", registry)
    assert node.node_type == GuardNodeType.NOT
    assert node.operand.node_type == GuardNodeType.CONDITION
    assert node.operand.variable == "status"
    assert node.operand.literal_value == "running"

def test_unknown_variable(registry):
    with pytest.raises(ParseError, match="Unknown variable"):
        parse_guard("unknown > 50", registry)

def test_type_mismatch_string(registry):
    with pytest.raises(ParseError, match="Invalid operator"):
        parse_guard("status > 'running'", registry)

def test_malformed_expression(registry):
    with pytest.raises(ParseError):
        parse_guard("temperature > 50 AND", registry)

def test_deeply_nested(registry):
    node = parse_guard("(a > 1 AND (b < 2 OR NOT (c == 'x')))", registry)
    assert node.node_type == GuardNodeType.AND
    assert node.left.variable == "a"
    assert node.right.node_type == GuardNodeType.OR
    assert node.right.left.variable == "b"
    assert node.right.right.node_type == GuardNodeType.NOT
    assert node.right.right.operand.variable == "c"

def test_empty_string(registry):
    with pytest.raises(ParseError, match="Empty guard expression"):
        parse_guard("", registry)
