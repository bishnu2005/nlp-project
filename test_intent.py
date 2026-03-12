import sys
import logging

logging.basicConfig(level=logging.INFO)

from manual_to_uml.chatbot.intent_mapper import map_intent, IntentMapper
from manual_to_uml.core.ibr_schema import IBR, State, Transition

# MOCK IBR
mock_ibr = IBR(
    version="1.0",
    manual_id="test",
    states=[
        State(id="Running", name="Running", is_initial=True, source_sentence_ids=["s01"]),
        State(id="Fault_Leak", name="Fault Leak", is_fault=True, source_sentence_ids=["s02"])
    ],
    transitions=[
        Transition(id="t1", from_state="Running", to_state="Fault_Leak", event="leak_detected", source_sentence_ids=["s02"]),
        Transition(id="t2", from_state="Fault_Leak", to_state="Running", event="replace_cartridge", source_sentence_ids=["s03"])
    ],
    variables={},
    source_sentences={"s01": "run", "s02": "leak", "s03": "replace string"}
)

mapper = IntentMapper()

print("--- Test 1: EXACT KEYWORD MATCH (Valid Transition) ---")
res1 = mapper.map_intent("what if i replace the cartridge now", mock_ibr, "Fault_Leak")
print(f"Result: {res1.matched_event} (Confidence: {res1.confidence})")

print("\n--- Test 2: FUZZY MATCH (Valid Transition) ---")
# Rapidfuzz should catch "replacce cardridge" -> "replace_cartridge" with >60
res2 = mapper.map_intent("i need to replacce cardridge", mock_ibr, "Fault_Leak")
print(f"Result: {res2.matched_event} (Confidence: {res2.confidence})")

print("\n--- Test 3: META QUERY ---")
res3 = mapper.map_intent("how do i use this simulator", mock_ibr, "Running")
print(f"Result META: {res3.is_meta}")

print("\n--- Test 4: SEMANTIC FALLBACK (Valid Transition) ---")
# "water is spraying everywhere" -> leak_detected (via semantic synonym mapped descriptive phrases)
res4 = mapper.map_intent("water is spraying everywhere", mock_ibr, "Running")
print(f"Result: {res4.matched_event} (Confidence: {res4.confidence})")
