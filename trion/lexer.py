"""
Lexical analyzer for the Trion programming language.
Provides robust tokenization with comprehensive error handling.
"""

import re
from typing import List, Optional, Iterator
from .token import Token
from .token_types import TokenType, KEYWORDS
from .errors import LexerError, ErrorReporter


class Lexer:
    """
    Robust lexical analyzer for Trion programming language.
    Features error recovery and detailed position tracking.
    """
    
    def __init__(self, source_code: str, filename: Optional[str] = None):
        self.source = source_code
        self.filename = filename
        self.position = 0
        self.line = 1
        self.column = 1
        self.tokens = []
        self.error_reporter = ErrorReporter()
    
    def current_char(self) -> Optional[str]:
        """Get current character or None if at end."""
        if self.position >= len(self.source):
            return None
        return self.source[self.position]
    
    def peek_char(self, offset: int = 1) -> Optional[str]:
        """Peek at character at current position + offset."""
        pos = self.position + offset
        if pos >= len(self.source):
            return None
        return self.source[pos]
    
    def advance(self) -> Optional[str]:
        """Advance position and return current character."""
        if self.position >= len(self.source):
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
        """Skip whitespace except newlines."""
        while self.current_char() and self.current_char() in ' \t\r':
            self.advance()
    
    def skip_comment(self):
        """Skip single-line comments starting with //"""
        if self.current_char() == '/' and self.peek_char() == '/':
            while self.current_char() and self.current_char() != '\n':
                self.advance()
    
    def read_string(self, quote_char: str) -> str:
        """Read string literal with escape sequence handling."""
        value = ""
        self.advance()  # Skip opening quote
        
        while self.current_char() and self.current_char() != quote_char:
            char = self.current_char()
            
            if char == '\\':
                # Handle escape sequences
                self.advance()
                next_char = self.current_char()
                
                if next_char == 'n':
                    value += '\n'
                elif next_char == 't':
                    value += '\t'
                elif next_char == 'r':
                    value += '\r'
                elif next_char == '\\':
                    value += '\\'
                elif next_char == quote_char:
                    value += quote_char
                elif next_char == '0':
                    value += '\0'
                else:
                    # Unknown escape, keep both characters
                    value += char + (next_char or '')
                
                self.advance()
            else:
                value += char
                self.advance()
        
        if self.current_char() == quote_char:
            self.advance()  # Skip closing quote
        else:
            self.error_reporter.error(
                f"Unterminated string literal",
                self.line, self.column, self.filename
            )
        
        return value
    
    def read_number(self) -> tuple[TokenType, str]:
        """Read numeric literal (integer or float)."""
        value = ""
        has_dot = False
        
        while self.current_char() and (self.current_char().isdigit() or self.current_char() == '.'):
            char = self.current_char()
            
            if char == '.':
                if has_dot:
                    break  # Second dot, stop reading
                has_dot = True
            
            value += char
            self.advance()
        
        # Handle scientific notation
        if self.current_char() and self.current_char().lower() == 'e':
            value += self.current_char()
            self.advance()
            
            if self.current_char() and self.current_char() in '+-':
                value += self.current_char()
                self.advance()
            
            while self.current_char() and self.current_char().isdigit():
                value += self.current_char()
                self.advance()
            
            has_dot = True  # Scientific notation is always float
        
        return (TokenType.FLOAT if has_dot else TokenType.INTEGER, value)
    
    def read_identifier(self) -> str:
        """Read identifier or keyword."""
        value = ""
        
        while (self.current_char() and 
               (self.current_char().isalnum() or self.current_char() == '_')):
            value += self.current_char()
            self.advance()
        
        return value
    
    def create_token(self, token_type: TokenType, value: str) -> Token:
        """Create token with current position information."""
        return Token(token_type, value, self.line, self.column, self.filename)
    
    def tokenize(self) -> List[Token]:
        """
        Tokenize the entire source code.
        Returns list of tokens with comprehensive error handling.
        """
        tokens = []
        
        while self.position < len(self.source):
            self.skip_whitespace()
            
            char = self.current_char()
            if not char:
                break
            
            # Skip comments
            if char == '/' and self.peek_char() == '/':
                self.skip_comment()
                continue
            
            start_line = self.line
            start_column = self.column
            
            # Newlines
            if char == '\n':
                tokens.append(Token(TokenType.NEWLINE, char, start_line, start_column, self.filename))
                self.advance()
            
            # String literals
            elif char in '"\'':
                value = self.read_string(char)
                tokens.append(Token(TokenType.STRING, value, start_line, start_column, self.filename))
            
            # Numbers
            elif char.isdigit():
                token_type, value = self.read_number()
                tokens.append(Token(token_type, value, start_line, start_column, self.filename))
            
            # Identifiers and keywords
            elif char.isalpha() or char == '_':
                value = self.read_identifier()
                token_type = KEYWORDS.get(value, TokenType.IDENTIFIER)
                tokens.append(Token(token_type, value, start_line, start_column, self.filename))
            
            # Two-character operators
            elif char == '+' and self.peek_char() == '=':
                tokens.append(Token(TokenType.PLUS_ASSIGN, '+=', start_line, start_column, self.filename))
                self.advance()
                self.advance()
            elif char == '-' and self.peek_char() == '=':
                tokens.append(Token(TokenType.MINUS_ASSIGN, '-=', start_line, start_column, self.filename))
                self.advance()
                self.advance()
            elif char == '*' and self.peek_char() == '=':
                tokens.append(Token(TokenType.MULTIPLY_ASSIGN, '*=', start_line, start_column, self.filename))
                self.advance()
                self.advance()
            elif char == '/' and self.peek_char() == '=':
                tokens.append(Token(TokenType.DIVIDE_ASSIGN, '/=', start_line, start_column, self.filename))
                self.advance()
                self.advance()
            elif char == '=' and self.peek_char() == '=':
                tokens.append(Token(TokenType.EQUAL, '==', start_line, start_column, self.filename))
                self.advance()
                self.advance()
            elif char == '!' and self.peek_char() == '=':
                tokens.append(Token(TokenType.NOT_EQUAL, '!=', start_line, start_column, self.filename))
                self.advance()
                self.advance()
            elif char == '<' and self.peek_char() == '=':
                tokens.append(Token(TokenType.LESS_EQUAL, '<=', start_line, start_column, self.filename))
                self.advance()
                self.advance()
            elif char == '>' and self.peek_char() == '=':
                tokens.append(Token(TokenType.GREATER_EQUAL, '>=', start_line, start_column, self.filename))
                self.advance()
                self.advance()
            elif char == '-' and self.peek_char() == '>':
                tokens.append(Token(TokenType.ARROW, '->', start_line, start_column, self.filename))
                self.advance()
                self.advance()
            elif char == '*' and self.peek_char() == '*':
                tokens.append(Token(TokenType.POWER, '**', start_line, start_column, self.filename))
                self.advance()
                self.advance()
            
            # Single-character operators and punctuation
            elif char == '+':
                tokens.append(Token(TokenType.PLUS, char, start_line, start_column, self.filename))
                self.advance()
            elif char == '-':
                tokens.append(Token(TokenType.MINUS, char, start_line, start_column, self.filename))
                self.advance()
            elif char == '*':
                tokens.append(Token(TokenType.MULTIPLY, char, start_line, start_column, self.filename))
                self.advance()
            elif char == '/':
                tokens.append(Token(TokenType.DIVIDE, char, start_line, start_column, self.filename))
                self.advance()
            elif char == '%':
                tokens.append(Token(TokenType.MODULO, char, start_line, start_column, self.filename))
                self.advance()
            elif char == '=':
                tokens.append(Token(TokenType.ASSIGN, char, start_line, start_column, self.filename))
                self.advance()
            elif char == '<':
                tokens.append(Token(TokenType.LESS_THAN, char, start_line, start_column, self.filename))
                self.advance()
            elif char == '>':
                tokens.append(Token(TokenType.GREATER_THAN, char, start_line, start_column, self.filename))
                self.advance()
            elif char == '(':
                tokens.append(Token(TokenType.LEFT_PAREN, char, start_line, start_column, self.filename))
                self.advance()
            elif char == ')':
                tokens.append(Token(TokenType.RIGHT_PAREN, char, start_line, start_column, self.filename))
                self.advance()
            elif char == '{':
                tokens.append(Token(TokenType.LEFT_BRACE, char, start_line, start_column, self.filename))
                self.advance()
            elif char == '}':
                tokens.append(Token(TokenType.RIGHT_BRACE, char, start_line, start_column, self.filename))
                self.advance()
            elif char == '[':
                tokens.append(Token(TokenType.LEFT_BRACKET, char, start_line, start_column, self.filename))
                self.advance()
            elif char == ']':
                tokens.append(Token(TokenType.RIGHT_BRACKET, char, start_line, start_column, self.filename))
                self.advance()
            elif char == ';':
                tokens.append(Token(TokenType.SEMICOLON, char, start_line, start_column, self.filename))
                self.advance()
            elif char == ',':
                tokens.append(Token(TokenType.COMMA, char, start_line, start_column, self.filename))
                self.advance()
            elif char == '.':
                tokens.append(Token(TokenType.DOT, char, start_line, start_column, self.filename))
                self.advance()
            elif char == ':':
                tokens.append(Token(TokenType.COLON, char, start_line, start_column, self.filename))
                self.advance()
            
            # Unknown character
            else:
                self.error_reporter.error(
                    f"Unexpected character: '{char}'",
                    start_line, start_column, self.filename
                )
                tokens.append(Token(TokenType.INVALID, char, start_line, start_column, self.filename))
                self.advance()
        
        # Add EOF token
        tokens.append(Token(TokenType.EOF, "", self.line, self.column, self.filename))
        self.tokens = tokens
        return tokens