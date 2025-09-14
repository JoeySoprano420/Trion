#!/usr/bin/env python3
"""
Trion Language Lexer

This module implements the lexical analyzer for the Trion programming language.
It converts source code into a stream of tokens that can be parsed.
"""

import re
from enum import Enum, auto
from dataclasses import dataclass
from typing import List, Optional, Iterator, Union

class TokenType(Enum):
    # Literals
    INTEGER = auto()
    FLOAT = auto()
    STRING = auto()
    CHAR = auto()
    BOOLEAN = auto()
    
    # Identifiers and Keywords
    IDENTIFIER = auto()
    
    # Keywords
    FN = auto()
    LET = auto()
    MUT = auto()
    IF = auto()
    ELSE = auto()
    MATCH = auto()
    FOR = auto()
    WHILE = auto()
    LOOP = auto()
    BREAK = auto()
    CONTINUE = auto()
    RETURN = auto()
    TRUE = auto()
    FALSE = auto()
    STRUCT = auto()
    ENUM = auto()
    IMPL = auto()
    TRAIT = auto()
    MOD = auto()
    USE = auto()
    PUB = auto()
    EXTERN = auto()
    ASYNC = auto()
    AWAIT = auto()
    
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
    LESS = auto()
    LESS_EQUAL = auto()
    GREATER = auto()
    GREATER_EQUAL = auto()
    
    # Logical
    AND = auto()
    OR = auto()
    NOT = auto()
    
    # Bitwise
    BIT_AND = auto()
    BIT_OR = auto()
    BIT_XOR = auto()
    BIT_NOT = auto()
    LEFT_SHIFT = auto()
    RIGHT_SHIFT = auto()
    
    # Delimiters
    LPAREN = auto()
    RPAREN = auto()
    LBRACE = auto()
    RBRACE = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    SEMICOLON = auto()
    COMMA = auto()
    DOT = auto()
    COLON = auto()
    DOUBLE_COLON = auto()
    ARROW = auto()
    FAT_ARROW = auto()
    QUESTION = auto()
    
    # Special
    NEWLINE = auto()
    EOF = auto()
    COMMENT = auto()
    
    # Error
    ERROR = auto()

@dataclass
class Token:
    type: TokenType
    value: str
    line: int
    column: int
    
    def __str__(self) -> str:
        return f"Token({self.type.name}, '{self.value}', {self.line}:{self.column})"

class LexerError(Exception):
    def __init__(self, message: str, line: int, column: int):
        self.message = message
        self.line = line
        self.column = column
        super().__init__(f"Lexer error at {line}:{column}: {message}")

class Lexer:
    """Lexical analyzer for the Trion programming language."""
    
    # Keywords mapping
    KEYWORDS = {
        'fn': TokenType.FN,
        'let': TokenType.LET,
        'mut': TokenType.MUT,
        'if': TokenType.IF,
        'else': TokenType.ELSE,
        'match': TokenType.MATCH,
        'for': TokenType.FOR,
        'while': TokenType.WHILE,
        'loop': TokenType.LOOP,
        'break': TokenType.BREAK,
        'continue': TokenType.CONTINUE,
        'return': TokenType.RETURN,
        'true': TokenType.TRUE,
        'false': TokenType.FALSE,
        'struct': TokenType.STRUCT,
        'enum': TokenType.ENUM,
        'impl': TokenType.IMPL,
        'trait': TokenType.TRAIT,
        'mod': TokenType.MOD,
        'use': TokenType.USE,
        'pub': TokenType.PUB,
        'extern': TokenType.EXTERN,
        'async': TokenType.ASYNC,
        'await': TokenType.AWAIT,
    }
    
    def __init__(self, source: str):
        self.source = source
        self.position = 0
        self.line = 1
        self.column = 1
        self.length = len(source)
    
    def current_char(self) -> Optional[str]:
        """Get the current character without advancing."""
        if self.position >= self.length:
            return None
        return self.source[self.position]
    
    def peek_char(self, offset: int = 1) -> Optional[str]:
        """Peek at character ahead by offset."""
        pos = self.position + offset
        if pos >= self.length:
            return None
        return self.source[pos]
    
    def advance(self) -> Optional[str]:
        """Advance to next character and return current."""
        if self.position >= self.length:
            return None
        
        char = self.source[self.position]
        self.position += 1
        
        if char == '\n':
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        
        return char
    
    def skip_whitespace(self):
        """Skip whitespace characters except newlines."""
        while self.current_char() and self.current_char() in ' \t\r':
            self.advance()
    
    def read_number(self) -> Token:
        """Read integer or floating-point number."""
        start_column = self.column
        value = ''
        is_float = False
        
        # Read digits
        while self.current_char() and self.current_char().isdigit():
            value += self.advance()
        
        # Check for decimal point
        if self.current_char() == '.' and self.peek_char() and self.peek_char().isdigit():
            is_float = True
            value += self.advance()  # consume '.'
            
            # Read fractional part
            while self.current_char() and self.current_char().isdigit():
                value += self.advance()
        
        # Check for scientific notation
        if self.current_char() and self.current_char().lower() == 'e':
            is_float = True
            value += self.advance()  # consume 'e'
            
            # Optional sign
            if self.current_char() and self.current_char() in '+-':
                value += self.advance()
            
            # Read exponent digits
            while self.current_char() and self.current_char().isdigit():
                value += self.advance()
        
        # Check for type suffix
        if self.current_char() and self.current_char().lower() == 'f':
            is_float = True
            self.advance()  # consume 'f'
        
        token_type = TokenType.FLOAT if is_float else TokenType.INTEGER
        return Token(token_type, value, self.line, start_column)
    
    def read_string(self, quote_char: str) -> Token:
        """Read string literal."""
        start_column = self.column
        value = ''
        self.advance()  # consume opening quote
        
        while self.current_char() and self.current_char() != quote_char:
            if self.current_char() == '\\':
                self.advance()  # consume backslash
                escape_char = self.current_char()
                if escape_char is None:
                    raise LexerError("Unterminated string literal", self.line, self.column)
                
                # Handle escape sequences
                if escape_char == 'n':
                    value += '\n'
                elif escape_char == 't':
                    value += '\t'
                elif escape_char == 'r':
                    value += '\r'
                elif escape_char == '\\':
                    value += '\\'
                elif escape_char == '"':
                    value += '"'
                elif escape_char == "'":
                    value += "'"
                else:
                    value += escape_char
                
                self.advance()
            else:
                value += self.advance()
        
        if self.current_char() != quote_char:
            raise LexerError("Unterminated string literal", self.line, start_column)
        
        self.advance()  # consume closing quote
        
        token_type = TokenType.CHAR if quote_char == "'" and len(value) == 1 else TokenType.STRING
        return Token(token_type, value, self.line, start_column)
    
    def read_identifier(self) -> Token:
        """Read identifier or keyword."""
        start_column = self.column
        value = ''
        
        # First character must be letter or underscore
        if self.current_char() and (self.current_char().isalpha() or self.current_char() == '_'):
            value += self.advance()
        
        # Subsequent characters can be letters, digits, or underscores
        while (self.current_char() and 
               (self.current_char().isalnum() or self.current_char() == '_')):
            value += self.advance()
        
        # Check if it's a keyword
        token_type = self.KEYWORDS.get(value, TokenType.IDENTIFIER)
        return Token(token_type, value, self.line, start_column)
    
    def read_comment(self) -> Token:
        """Read single-line or multi-line comment."""
        start_column = self.column
        value = ''
        
        if self.current_char() == '/' and self.peek_char() == '/':
            # Single-line comment
            self.advance()  # consume first '/'
            self.advance()  # consume second '/'
            
            while self.current_char() and self.current_char() != '\n':
                value += self.advance()
                
        elif self.current_char() == '/' and self.peek_char() == '*':
            # Multi-line comment
            self.advance()  # consume '/'
            self.advance()  # consume '*'
            
            while self.position < self.length - 1:
                if self.current_char() == '*' and self.peek_char() == '/':
                    self.advance()  # consume '*'
                    self.advance()  # consume '/'
                    break
                value += self.advance()
            else:
                raise LexerError("Unterminated multi-line comment", self.line, start_column)
        
        return Token(TokenType.COMMENT, value, self.line, start_column)
    
    def next_token(self) -> Token:
        """Get the next token from the source."""
        self.skip_whitespace()
        
        if self.position >= self.length:
            return Token(TokenType.EOF, '', self.line, self.column)
        
        char = self.current_char()
        start_column = self.column
        
        # Numbers
        if char.isdigit():
            return self.read_number()
        
        # Strings and characters
        if char in '"\'':
            return self.read_string(char)
        
        # Identifiers and keywords
        if char.isalpha() or char == '_':
            return self.read_identifier()
        
        # Comments
        if char == '/' and (self.peek_char() == '/' or self.peek_char() == '*'):
            return self.read_comment()
        
        # Two-character operators
        if char == '=' and self.peek_char() == '=':
            self.advance()
            self.advance()
            return Token(TokenType.EQUAL, '==', self.line, start_column)
        
        if char == '!' and self.peek_char() == '=':
            self.advance()
            self.advance()
            return Token(TokenType.NOT_EQUAL, '!=', self.line, start_column)
        
        if char == '<' and self.peek_char() == '=':
            self.advance()
            self.advance()
            return Token(TokenType.LESS_EQUAL, '<=', self.line, start_column)
        
        if char == '>' and self.peek_char() == '=':
            self.advance()
            self.advance()
            return Token(TokenType.GREATER_EQUAL, '>=', self.line, start_column)
        
        if char == '&' and self.peek_char() == '&':
            self.advance()
            self.advance()
            return Token(TokenType.AND, '&&', self.line, start_column)
        
        if char == '|' and self.peek_char() == '|':
            self.advance()
            self.advance()
            return Token(TokenType.OR, '||', self.line, start_column)
        
        if char == '-' and self.peek_char() == '>':
            self.advance()
            self.advance()
            return Token(TokenType.ARROW, '->', self.line, start_column)
        
        if char == '=' and self.peek_char() == '>':
            self.advance()
            self.advance()
            return Token(TokenType.FAT_ARROW, '=>', self.line, start_column)
        
        if char == ':' and self.peek_char() == ':':
            self.advance()
            self.advance()
            return Token(TokenType.DOUBLE_COLON, '::', self.line, start_column)
        
        # Single character tokens
        single_char_tokens = {
            '+': TokenType.PLUS,
            '-': TokenType.MINUS,
            '*': TokenType.MULTIPLY,
            '/': TokenType.DIVIDE,
            '%': TokenType.MODULO,
            '=': TokenType.ASSIGN,
            '<': TokenType.LESS,
            '>': TokenType.GREATER,
            '!': TokenType.NOT,
            '&': TokenType.BIT_AND,
            '|': TokenType.BIT_OR,
            '^': TokenType.BIT_XOR,
            '~': TokenType.BIT_NOT,
            '(': TokenType.LPAREN,
            ')': TokenType.RPAREN,
            '{': TokenType.LBRACE,
            '}': TokenType.RBRACE,
            '[': TokenType.LBRACKET,
            ']': TokenType.RBRACKET,
            ';': TokenType.SEMICOLON,
            ',': TokenType.COMMA,
            '.': TokenType.DOT,
            ':': TokenType.COLON,
            '?': TokenType.QUESTION,
            '\n': TokenType.NEWLINE,
        }
        
        if char in single_char_tokens:
            self.advance()
            return Token(single_char_tokens[char], char, self.line, start_column)
        
        # Unknown character
        self.advance()
        return Token(TokenType.ERROR, char, self.line, start_column)
    
    def tokenize(self) -> List[Token]:
        """Tokenize the entire source and return list of tokens."""
        tokens = []
        
        while True:
            token = self.next_token()
            tokens.append(token)
            
            if token.type == TokenType.EOF:
                break
                
            if token.type == TokenType.ERROR:
                raise LexerError(f"Unexpected character: '{token.value}'", 
                               token.line, token.column)
        
        return tokens

def main():
    """Test the lexer with sample code."""
    sample_code = '''
    fn main() {
        let x: i32 = 42;
        let mut y = 3.14;
        println("Hello, World!");
        
        if x > 0 {
            return x * 2;
        }
    }
    '''
    
    lexer = Lexer(sample_code)
    tokens = lexer.tokenize()
    
    for token in tokens:
        if token.type != TokenType.NEWLINE:
            print(token)

if __name__ == '__main__':
    main()