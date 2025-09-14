"""
Token definitions for the Trion programming language.
Provides robust token classification for error-free parsing.
"""

from enum import Enum, auto


class TokenType(Enum):
    # Literals
    INTEGER = auto()
    FLOAT = auto()
    STRING = auto()
    BOOLEAN = auto()
    NULL = auto()
    
    # Identifiers
    IDENTIFIER = auto()
    
    # Keywords
    IF = auto()
    ELSE = auto()
    ELIF = auto()
    WHILE = auto()
    FOR = auto()
    FUNCTION = auto()
    RETURN = auto()
    CLASS = auto()
    IMPORT = auto()
    FROM = auto()
    TRY = auto()
    CATCH = auto()
    FINALLY = auto()
    THROW = auto()
    TRUE = auto()
    FALSE = auto()
    NULL_KW = auto()
    LET = auto()
    CONST = auto()
    
    # Operators
    PLUS = auto()
    MINUS = auto()
    MULTIPLY = auto()
    DIVIDE = auto()
    MODULO = auto()
    POWER = auto()
    ASSIGN = auto()
    PLUS_ASSIGN = auto()
    MINUS_ASSIGN = auto()
    MULTIPLY_ASSIGN = auto()
    DIVIDE_ASSIGN = auto()
    
    # Comparison
    EQUAL = auto()
    NOT_EQUAL = auto()
    LESS_THAN = auto()
    LESS_EQUAL = auto()
    GREATER_THAN = auto()
    GREATER_EQUAL = auto()
    
    # Logical
    AND = auto()
    OR = auto()
    NOT = auto()
    
    # Punctuation
    LEFT_PAREN = auto()
    RIGHT_PAREN = auto()
    LEFT_BRACE = auto()
    RIGHT_BRACE = auto()
    LEFT_BRACKET = auto()
    RIGHT_BRACKET = auto()
    SEMICOLON = auto()
    COMMA = auto()
    DOT = auto()
    COLON = auto()
    ARROW = auto()
    
    # Special
    NEWLINE = auto()
    EOF = auto()
    INVALID = auto()


# Keyword mapping for resilient keyword recognition
KEYWORDS = {
    'if': TokenType.IF,
    'else': TokenType.ELSE,
    'elif': TokenType.ELIF,
    'while': TokenType.WHILE,
    'for': TokenType.FOR,
    'function': TokenType.FUNCTION,
    'return': TokenType.RETURN,
    'class': TokenType.CLASS,
    'import': TokenType.IMPORT,
    'from': TokenType.FROM,
    'try': TokenType.TRY,
    'catch': TokenType.CATCH,
    'finally': TokenType.FINALLY,
    'throw': TokenType.THROW,
    'true': TokenType.TRUE,
    'false': TokenType.FALSE,
    'null': TokenType.NULL_KW,
    'let': TokenType.LET,
    'const': TokenType.CONST,
    'and': TokenType.AND,
    'or': TokenType.OR,
    'not': TokenType.NOT,
}