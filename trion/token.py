"""
Token class for representing lexical tokens.
"""

from .token_types import TokenType


class Token:
    """Represents a single lexical token with position information."""
    
    def __init__(self, token_type, value, line=1, column=1, filename=None):
        self.type = token_type
        self.value = value
        self.line = line
        self.column = column
        self.filename = filename
    
    def __str__(self):
        return f"Token({self.type.name}, {repr(self.value)}, {self.line}:{self.column})"
    
    def __repr__(self):
        return self.__str__()
    
    def is_type(self, token_type):
        """Check if token is of specified type."""
        return self.type == token_type
    
    def is_literal(self):
        """Check if token is a literal value."""
        return self.type in {
            TokenType.INTEGER,
            TokenType.FLOAT,
            TokenType.STRING,
            TokenType.TRUE,
            TokenType.FALSE,
            TokenType.NULL_KW
        }
    
    def is_operator(self):
        """Check if token is an operator."""
        return self.type in {
            TokenType.PLUS,
            TokenType.MINUS,
            TokenType.MULTIPLY,
            TokenType.DIVIDE,
            TokenType.MODULO,
            TokenType.POWER,
            TokenType.ASSIGN,
            TokenType.PLUS_ASSIGN,
            TokenType.MINUS_ASSIGN,
            TokenType.MULTIPLY_ASSIGN,
            TokenType.DIVIDE_ASSIGN,
            TokenType.EQUAL,
            TokenType.NOT_EQUAL,
            TokenType.LESS_THAN,
            TokenType.LESS_EQUAL,
            TokenType.GREATER_THAN,
            TokenType.GREATER_EQUAL,
            TokenType.AND,
            TokenType.OR,
            TokenType.NOT
        }
    
    def is_keyword(self):
        """Check if token is a keyword."""
        return self.type in {
            TokenType.IF,
            TokenType.ELSE,
            TokenType.ELIF,
            TokenType.WHILE,
            TokenType.FOR,
            TokenType.FUNCTION,
            TokenType.RETURN,
            TokenType.CLASS,
            TokenType.IMPORT,
            TokenType.FROM,
            TokenType.TRY,
            TokenType.CATCH,
            TokenType.FINALLY,
            TokenType.THROW,
            TokenType.TRUE,
            TokenType.FALSE,
            TokenType.NULL_KW,
            TokenType.LET,
            TokenType.CONST,
            TokenType.AND,
            TokenType.OR,
            TokenType.NOT
        }