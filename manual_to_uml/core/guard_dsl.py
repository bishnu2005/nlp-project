import re
from typing import Dict, List, Optional
from manual_to_uml.core.ibr_schema import GuardNode, GuardNodeType, Variable, VariableType
from manual_to_uml.core.exceptions import ParseError

class TokenType(str):
    AND = "AND"
    OR = "OR"
    NOT = "NOT"
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    OPERATOR = "OPERATOR"
    LITERAL_STR = "LITERAL_STR"
    LITERAL_NUM = "LITERAL_NUM"
    LITERAL_BOOL = "LITERAL_BOOL"
    IDENTIFIER = "IDENTIFIER"
    EOF = "EOF"

class Token:
    def __init__(self, type_: str, value: str, position: int):
        self.type = type_
        self.value = value
        self.position = position
        
    def __repr__(self):
        return f"Token({self.type}, {self.value})"

class Lexer:
    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.current_char = self.text[self.pos] if self.text else None
        
    def advance(self):
        self.pos += 1
        self.current_char = self.text[self.pos] if self.pos < len(self.text) else None
        
    def skip_whitespace(self):
        while self.current_char is not None and self.current_char.isspace():
            self.advance()
            
    def number(self) -> Token:
        pos = self.pos
        result = ''
        if self.current_char == '-':
            result += '-'
            self.advance()
        while self.current_char is not None and (self.current_char.isdigit() or self.current_char == '.'):
            result += self.current_char
            self.advance()
        return Token(TokenType.LITERAL_NUM, result, pos)
        
    def string(self) -> Token:
        pos = self.pos
        quote = self.current_char
        self.advance()
        result = ''
        while self.current_char is not None and self.current_char != quote:
            result += self.current_char
            self.advance()
        if self.current_char == quote:
            self.advance()
        else:
            raise ParseError("Unterminated string literal", pos)
        return Token(TokenType.LITERAL_STR, result, pos)
        
    def identifier(self) -> Token:
        pos = self.pos
        result = ''
        while self.current_char is not None and (self.current_char.isalnum() or self.current_char == '_'):
            result += self.current_char
            self.advance()
            
        upper_val = result.upper()
        if upper_val == "AND":
            return Token(TokenType.AND, "AND", pos)
        if upper_val == "OR":
            return Token(TokenType.OR, "OR", pos)
        if upper_val == "NOT":
            return Token(TokenType.NOT, "NOT", pos)
        if upper_val in ("TRUE", "FALSE"):
            return Token(TokenType.LITERAL_BOOL, result, pos)
            
        return Token(TokenType.IDENTIFIER, result, pos)
        
    def get_next_token(self) -> Token:
        while self.current_char is not None:
            if self.current_char.isspace():
                self.skip_whitespace()
                continue
                
            if self.current_char.isalpha() or self.current_char == '_':
                return self.identifier()
                
            if self.current_char.isdigit() or self.current_char == '-':
                if self.current_char == '-' and (self.pos + 1 >= len(self.text) or not self.text[self.pos+1].isdigit()):
                    raise ParseError("Invalid character '-'", self.pos)
                return self.number()
                
            if self.current_char in ("'", '"'):
                return self.string()
                
            if self.current_char == '(':
                pos = self.pos
                self.advance()
                return Token(TokenType.LPAREN, '(', pos)
                
            if self.current_char == ')':
                pos = self.pos
                self.advance()
                return Token(TokenType.RPAREN, ')', pos)
                
            # Operators: >, <, >=, <=, ==, !=
            pos = self.pos
            if self.current_char in ('>', '<', '=', '!'):
                char1 = self.current_char
                self.advance()
                if self.current_char == '=':
                    val = char1 + '='
                    self.advance()
                    return Token(TokenType.OPERATOR, val, pos)
                if char1 in ('>', '<'):
                    return Token(TokenType.OPERATOR, char1, pos)
                raise ParseError(f"Invalid operator start '{char1}'", pos)
                
            raise ParseError(f"Invalid character '{self.current_char}'", self.pos)
            
        return Token(TokenType.EOF, "", self.pos)

class Parser:
    def __init__(self, lexer: Lexer, registry: Dict[str, Variable]):
        self.lexer = lexer
        self.registry = registry
        self.current_token = self.lexer.get_next_token()
        
    def error(self, message: str, position: int = None):
        if position is None:
            position = self.current_token.position
        raise ParseError(message, position)
        
    def eat(self, token_type: str):
        if self.current_token.type == token_type:
            self.current_token = self.lexer.get_next_token()
        else:
            self.error(f"Expected {token_type}, got {self.current_token.type}")
            
    def parse(self) -> GuardNode:
        if self.current_token.type == TokenType.EOF:
            self.error("Empty guard expression")
        node = self.compound()
        if self.current_token.type != TokenType.EOF:
            self.error("Unexpected token after valid expression")
        return node
        
    def compound(self) -> GuardNode:
        node = self.unary()
        while self.current_token.type in (TokenType.AND, TokenType.OR):
            op_token = self.current_token
            if op_token.type == TokenType.AND:
                self.eat(TokenType.AND)
                node_type = GuardNodeType.AND
            else:
                self.eat(TokenType.OR)
                node_type = GuardNodeType.OR
                
            right = self.unary()
            new_node = GuardNode(
                node_type=node_type,
                left=node,
                right=right
            )
            node = new_node
        return node
        
    def unary(self) -> GuardNode:
        if self.current_token.type == TokenType.NOT:
            self.eat(TokenType.NOT)
            node = self.primary()
            return GuardNode(
                node_type=GuardNodeType.NOT,
                operand=node
            )
        return self.primary()
        
    def primary(self) -> GuardNode:
        if self.current_token.type == TokenType.LPAREN:
            self.eat(TokenType.LPAREN)
            node = self.compound()
            self.eat(TokenType.RPAREN)
            return node
        return self.condition()
        
    def condition(self) -> GuardNode:
        id_token = self.current_token
        self.eat(TokenType.IDENTIFIER)
        var_name = id_token.value
        
        if var_name not in self.registry:
            self.error(f"Unknown variable '{var_name}'", id_token.position)
            
        op_token = self.current_token
        self.eat(TokenType.OPERATOR)
        operator = op_token.value
        
        val_token = self.current_token
        if val_token.type == TokenType.LITERAL_NUM:
            self.eat(TokenType.LITERAL_NUM)
            if '.' in val_token.value:
                literal_val = float(val_token.value)
            else:
                literal_val = int(val_token.value)
        elif val_token.type == TokenType.LITERAL_STR:
            self.eat(TokenType.LITERAL_STR)
            literal_val = val_token.value
            if operator not in ('==', '!='):
                self.error(f"Invalid operator '{operator}' for string comparison", op_token.position)
        elif val_token.type == TokenType.LITERAL_BOOL:
            self.eat(TokenType.LITERAL_BOOL)
            literal_val = val_token.value.lower() == 'true'
            if operator not in ('==', '!='):
                self.error(f"Invalid operator '{operator}' for boolean comparison", op_token.position)
        else:
            self.error("Expected literal value", val_token.position)
            
        return GuardNode(
            node_type=GuardNodeType.CONDITION,
            variable=var_name,
            operator=operator,
            literal_value=literal_val
        )

def parse_guard(text: str, registry: Dict[str, Variable]) -> GuardNode:
    lexer = Lexer(text)
    parser = Parser(lexer, registry)
    return parser.parse()
