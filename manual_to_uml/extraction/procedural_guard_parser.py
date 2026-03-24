import re
from typing import Optional, Dict, Any

# Matches "pressure > 5" or "temp <= 60"
NUMERIC_PATTERN = re.compile(
    r"(\w+)\s*(<=|>=|==|>|<)\s*(\d+)"
)

# Matches "leak == true" or "valve == False"
BOOLEAN_PATTERN = re.compile(
    r"(\w+)\s*==\s*(true|false)",
    re.IGNORECASE
)

def parse_guard(text: str) -> Optional[Dict[str, Any]]:
    """
    Deterministically parses comparative condition properties without involving
    complex recursive AST tracking or LLMs.
    """
    m = NUMERIC_PATTERN.search(text)
    if m:
        return {
            "variable": m.group(1),
            "operator": m.group(2),
            "value": float(m.group(3))
        }

    m = BOOLEAN_PATTERN.search(text)
    if m:
        return {
            "variable": m.group(1),
            "operator": "==",
            "value": m.group(2).lower() == "true"
        }

    return None
