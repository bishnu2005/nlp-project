import re
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class Tokenizer:
    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.tokens = self._tokenize(text)
        
    def _tokenize(self, text: str) -> list:
        # Simple tokenization: match words, numbers, operators, parens
        pattern = r'([a-zA-Z_]\w*|\d+(?:\.\d+)?|>=|<=|==|!=|>|<|\(|\)|AND|OR|and|or)'
        matches = re.finditer(pattern, text)
        return [m.group(1) for m in matches]
        
    def peek(self) -> Optional[str]:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None
        
    def consume(self) -> Optional[str]:
        token = self.peek()
        if token is not None:
            self.pos += 1
        return token

class GuardParser:
    """
    Parses textual guard conditions into GuardNode AST dictionaries.
    Example: "pressure > 5 AND temperature < 10"
    """
    def parse(self, text: str) -> Optional[Dict[str, Any]]:
        self.tokenizer = Tokenizer(text)
        try:
            res = self._parse_expression()
            from manual_to_uml.config import DEBUG_PIPELINE
            if DEBUG_PIPELINE and res and res.get("node_type") == "condition":
                logger.info("[DEBUG] Guard AST")
                logger.info({
                    "variable": res.get("variable"),
                    "operator": res.get("operator"),
                    "value": res.get("literal_value")
                })
            return res
        except Exception as e:
            logger.warning(f"Failed to parse guard '{text}': {e}")
            return None

    def _parse_expression(self) -> Optional[Dict[str, Any]]:
        left = self._parse_term()
        if not left:
            return None
            
        while True:
            op = self.tokenizer.peek()
            if op and op.upper() in ("AND", "OR"):
                self.tokenizer.consume()
                right = self._parse_term()
                if not right:
                    raise SyntaxError(f"Expected term after {op}")
                left = {
                    "node_type": op.upper(),
                    "left": left,
                    "right": right
                }
            else:
                break
        return left

    def _parse_term(self) -> Optional[Dict[str, Any]]:
        token = self.tokenizer.peek()
        if not token:
            return None
            
        if token == "(":
            self.tokenizer.consume()
            expr = self._parse_expression()
            if self.tokenizer.peek() == ")":
                self.tokenizer.consume()
            else:
                raise SyntaxError("Missing closing parenthesis")
            return expr
            
        # Parse comparison: variable operator value
        var = self.tokenizer.consume()
        if not var:
            return None
            
        op = self.tokenizer.peek()
        if not op or op not in (">", "<", ">=", "<=", "==", "!="):
             # Try single boolean variable mode if no operator
             return {
                 "node_type": "condition",
                 "variable": var,
                 "operator": "==",
                 "literal_value": True,
                 "left": None,
                 "right": None
             }
             
        self.tokenizer.consume() # consume the operator
        val = self.tokenizer.consume()
        if not val:
            raise SyntaxError("Expected value after operator")
            
        # Convert val to correct type if possible
        try:
            if "." in val:
                val = float(val)
            else:
                val = int(val)
        except ValueError:
            pass # Keep as string
            
        return {
            "node_type": "condition",
            "variable": var,
            "operator": op,
            "literal_value": val,
            "left": None,
            "right": None
        }
