import pytest
import os
from manual_to_uml.core.ibr_schema import IBR, State, Transition, GuardNode, GuardNodeType, Variable, VariableType
from manual_to_uml.generation.uml_generator import ibr_to_plantuml, ibr_to_json_simulator, render_plantuml

@pytest.fixture
def sample_ibr():
    return IBR(
        version="1.0",
        manual_id="m1",
        states=[
            State(id="s1", name="Initial", is_initial=True, entry_action="init()", source_sentence_ids=["s001"]),
            State(id="s2", name="Running", exit_action="cleanup()"),
            State(id="s3", name="End", is_terminal=True)
        ],
        transitions=[
            Transition(id="t1", from_state="s1", to_state="s2", event="start", 
                       guard=GuardNode(node_type=GuardNodeType.CONDITION, variable="v", operator=">", literal_value=0), action="log()", source_sentence_ids=["s002"]),
            Transition(id="t2", from_state="s2", to_state="s3", event="stop")
        ],
        variables={"v": Variable(name="v", type=VariableType.INT)},
        source_sentences={"s001": "Start state.", "s002": "Transition on start."}
    )

def test_puml_generation_syntax(sample_ibr):
    puml = ibr_to_plantuml(sample_ibr)
    assert "@startuml" in puml
    assert "@enduml" in puml
    assert "[*] --> s1" in puml
    assert "s3 --> [*]" in puml

def test_puml_guard_syntax(sample_ibr):
    puml = ibr_to_plantuml(sample_ibr)
    # Check "event [guard] / action" syntax
    assert "s1 --> s2 : start [v > 0] / log()" in puml
    
def test_json_simulator_output(sample_ibr):
    json_data = ibr_to_json_simulator(sample_ibr)
    assert "states" in json_data
    assert "transitions" in json_data
    assert "variables" in json_data
    assert "initial_state" in json_data
    assert "source_sentences" in json_data
    assert json_data["initial_state"] == "s1"
    assert len(json_data["states"]) == 3
    assert len(json_data["transitions"]) == 2

def test_entry_exit_actions_in_puml(sample_ibr):
    puml = ibr_to_plantuml(sample_ibr)
    assert "entry / init()" in puml
    assert "exit / cleanup()" in puml

def test_plantuml_renders_without_error(sample_ibr, tmp_path):
    puml = ibr_to_plantuml(sample_ibr)
    output_png = str(tmp_path / "test_diagram.png")
    result = render_plantuml(puml, output_png)
    assert result is True
    # check that the puml file fallback is written
    assert os.path.exists(output_png.replace(".png", ".puml"))
