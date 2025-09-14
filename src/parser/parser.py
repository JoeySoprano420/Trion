#!/usr/bin/env python3
"""
Trion Language Parser

This module implements a recursive descent parser for the Trion programming language.
It converts a stream of tokens from the lexer into an Abstract Syntax Tree (AST).
"""

import sys
import os

# Add the src directory to path so we can import our modules
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
sys.path.insert(0, src_dir)

from typing import List, Optional, Union
from lexer.lexer import Token, TokenType, Lexer
from syntax_tree.syntax_tree import *

class ParseError(Exception):
    """Exception raised when parsing fails."""
    
    def __init__(self, message: str, token: Token):
        self.message = message
        self.token = token
        super().__init__(f"Parse error at {token.line}:{token.column}: {message}")

class Parser:
    """Recursive descent parser for Trion language."""
    
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.current = 0
        self.length = len(tokens)
    
    def is_at_end(self) -> bool:
        """Check if we've reached the end of tokens."""
        return self.peek().type == TokenType.EOF
    
    def peek(self) -> Token:
        """Get current token without consuming it."""
        if self.current >= self.length:
            return self.tokens[-1]  # EOF token
        return self.tokens[self.current]
    
    def previous(self) -> Token:
        """Get the previous token."""
        return self.tokens[self.current - 1]
    
    def advance(self) -> Token:
        """Consume current token and return it."""
        if not self.is_at_end():
            self.current += 1
        return self.previous()
    
    def check(self, token_type: TokenType) -> bool:
        """Check if current token is of given type."""
        if self.is_at_end():
            return False
        return self.peek().type == token_type
    
    def match(self, *token_types: TokenType) -> bool:
        """Check if current token matches any of the given types."""
        for token_type in token_types:
            if self.check(token_type):
                self.advance()
                return True
        return False
    
    def consume(self, token_type: TokenType, message: str) -> Token:
        """Consume token of expected type or raise error."""
        if self.check(token_type):
            return self.advance()
        
        current_token = self.peek()
        raise ParseError(message, current_token)
    
    def synchronize(self):
        """Recover from parse error by finding next statement boundary."""
        self.advance()
        
        while not self.is_at_end():
            if self.previous().type == TokenType.SEMICOLON:
                return
            
            if self.peek().type in [
                TokenType.FN, TokenType.LET, TokenType.IF, TokenType.WHILE,
                TokenType.FOR, TokenType.RETURN, TokenType.STRUCT, TokenType.ENUM
            ]:
                return
            
            self.advance()
    
    def skip_newlines(self):
        """Skip any newline tokens."""
        while self.match(TokenType.NEWLINE):
            pass
    
    def source_location(self, token: Token) -> SourceLocation:
        """Create source location from token."""
        return SourceLocation(token.line, token.column)
    
    def parse(self) -> Program:
        """Parse tokens into a program AST."""
        statements = []
        
        while not self.is_at_end():
            self.skip_newlines()
            if not self.is_at_end():
                try:
                    stmt = self.declaration()
                    if stmt:
                        statements.append(stmt)
                except ParseError as e:
                    print(f"Parse error: {e}")
                    self.synchronize()
        
        location = SourceLocation(1, 1) if not statements else statements[0].location
        return Program(statements, location)
    
    def declaration(self) -> Optional[Statement]:
        """Parse a declaration."""
        try:
            if self.match(TokenType.FN):
                return self.function_declaration()
            if self.match(TokenType.LET):
                return self.variable_declaration()
            
            return self.statement()
        except ParseError:
            self.synchronize()
            return None
    
    def function_declaration(self) -> FunctionDeclaration:
        """Parse function declaration."""
        name_token = self.consume(TokenType.IDENTIFIER, "Expected function name")
        name = name_token.value
        
        self.consume(TokenType.LPAREN, "Expected '(' after function name")
        
        parameters = []
        if not self.check(TokenType.RPAREN):
            parameters.append(self.parameter())
            
            while self.match(TokenType.COMMA):
                if len(parameters) >= 255:
                    raise ParseError("Can't have more than 255 parameters", self.peek())
                parameters.append(self.parameter())
        
        self.consume(TokenType.RPAREN, "Expected ')' after parameters")
        
        return_type = None
        if self.match(TokenType.ARROW):
            return_type = self.type_annotation()
        
        self.skip_newlines()
        self.consume(TokenType.LBRACE, "Expected '{' before function body")
        body = self.block_statement()
        
        location = self.source_location(name_token)
        return FunctionDeclaration(name, parameters, return_type, body, False, location)
    
    def parameter(self) -> Parameter:
        """Parse function parameter."""
        name_token = self.consume(TokenType.IDENTIFIER, "Expected parameter name")
        
        type_annotation = None
        if self.match(TokenType.COLON):
            type_annotation = self.type_annotation()
        
        return Parameter(name_token.value, type_annotation)
    
    def type_annotation(self) -> TypeAnnotation:
        """Parse type annotation."""
        name_token = self.consume(TokenType.IDENTIFIER, "Expected type name")
        return TypeAnnotation(name_token.value)
    
    def variable_declaration(self) -> VariableDeclaration:
        """Parse variable declaration."""
        is_mutable = self.match(TokenType.MUT)
        
        name_token = self.consume(TokenType.IDENTIFIER, "Expected variable name")
        name = name_token.value
        
        type_annotation = None
        if self.match(TokenType.COLON):
            type_annotation = self.type_annotation()
        
        initializer = None
        if self.match(TokenType.ASSIGN):
            initializer = self.expression()
        
        self.consume(TokenType.SEMICOLON, "Expected ';' after variable declaration")
        
        location = self.source_location(name_token)
        return VariableDeclaration(name, type_annotation, initializer, is_mutable, location)
    
    def statement(self) -> Statement:
        """Parse a statement."""
        if self.match(TokenType.IF):
            return self.if_statement()
        if self.match(TokenType.WHILE):
            return self.while_statement()
        if self.match(TokenType.RETURN):
            return self.return_statement()
        if self.match(TokenType.BREAK):
            return self.break_statement()
        if self.match(TokenType.CONTINUE):
            return self.continue_statement()
        if self.match(TokenType.LBRACE):
            return self.block_statement()
        
        return self.expression_statement()
    
    def if_statement(self) -> IfStatement:
        """Parse if statement."""
        condition = self.expression()
        
        self.skip_newlines()
        then_branch = self.statement()
        
        else_branch = None
        if self.match(TokenType.ELSE):
            self.skip_newlines()
            else_branch = self.statement()
        
        location = self.source_location(self.previous())
        return IfStatement(condition, then_branch, else_branch, location)
    
    def while_statement(self) -> WhileStatement:
        """Parse while statement."""
        condition = self.expression()
        
        self.skip_newlines()
        body = self.statement()
        
        location = self.source_location(self.previous())
        return WhileStatement(condition, body, location)
    
    def return_statement(self) -> ReturnStatement:
        """Parse return statement."""
        keyword = self.previous()
        
        value = None
        if not self.check(TokenType.SEMICOLON):
            value = self.expression()
        
        self.consume(TokenType.SEMICOLON, "Expected ';' after return value")
        
        location = self.source_location(keyword)
        return ReturnStatement(value, location)
    
    def break_statement(self) -> BreakStatement:
        """Parse break statement."""
        keyword = self.previous()
        self.consume(TokenType.SEMICOLON, "Expected ';' after 'break'")
        
        location = self.source_location(keyword)
        return BreakStatement(location)
    
    def continue_statement(self) -> ContinueStatement:
        """Parse continue statement."""
        keyword = self.previous()
        self.consume(TokenType.SEMICOLON, "Expected ';' after 'continue'")
        
        location = self.source_location(keyword)
        return ContinueStatement(location)
    
    def block_statement(self) -> BlockStatement:
        """Parse block statement."""
        start_token = self.previous()  # Should be '{'
        statements = []
        
        self.skip_newlines()
        
        while not self.check(TokenType.RBRACE) and not self.is_at_end():
            self.skip_newlines()
            if not self.check(TokenType.RBRACE):
                stmt = self.declaration()
                if stmt:
                    statements.append(stmt)
            self.skip_newlines()
        
        self.consume(TokenType.RBRACE, "Expected '}' after block")
        
        location = self.source_location(start_token)
        return BlockStatement(statements, location)
    
    def expression_statement(self) -> ExpressionStatement:
        """Parse expression statement."""
        expr = self.expression()
        self.consume(TokenType.SEMICOLON, "Expected ';' after expression")
        
        location = expr.location
        return ExpressionStatement(expr, location)
    
    def expression(self) -> Expression:
        """Parse expression."""
        return self.assignment()
    
    def assignment(self) -> Expression:
        """Parse assignment expression."""
        expr = self.logical_or()
        
        if self.match(TokenType.ASSIGN):
            equals = self.previous()
            value = self.assignment()
            
            location = self.source_location(equals)
            return AssignmentExpression(expr, value, location)
        
        return expr
    
    def logical_or(self) -> Expression:
        """Parse logical OR expression."""
        expr = self.logical_and()
        
        while self.match(TokenType.OR):
            operator = BinaryOperator.LOGICAL_OR
            right = self.logical_and()
            location = expr.location
            expr = BinaryExpression(expr, operator, right, location)
        
        return expr
    
    def logical_and(self) -> Expression:
        """Parse logical AND expression."""
        expr = self.equality()
        
        while self.match(TokenType.AND):
            operator = BinaryOperator.LOGICAL_AND
            right = self.equality()
            location = expr.location
            expr = BinaryExpression(expr, operator, right, location)
        
        return expr
    
    def equality(self) -> Expression:
        """Parse equality expression."""
        expr = self.comparison()
        
        while self.match(TokenType.EQUAL, TokenType.NOT_EQUAL):
            operator_token = self.previous()
            operator = (BinaryOperator.EQUAL if operator_token.type == TokenType.EQUAL 
                       else BinaryOperator.NOT_EQUAL)
            right = self.comparison()
            location = expr.location
            expr = BinaryExpression(expr, operator, right, location)
        
        return expr
    
    def comparison(self) -> Expression:
        """Parse comparison expression."""
        expr = self.term()
        
        while self.match(TokenType.GREATER, TokenType.GREATER_EQUAL, 
                         TokenType.LESS, TokenType.LESS_EQUAL):
            operator_token = self.previous()
            operator_map = {
                TokenType.GREATER: BinaryOperator.GREATER_THAN,
                TokenType.GREATER_EQUAL: BinaryOperator.GREATER_EQUAL,
                TokenType.LESS: BinaryOperator.LESS_THAN,
                TokenType.LESS_EQUAL: BinaryOperator.LESS_EQUAL,
            }
            operator = operator_map[operator_token.type]
            right = self.term()
            location = expr.location
            expr = BinaryExpression(expr, operator, right, location)
        
        return expr
    
    def term(self) -> Expression:
        """Parse addition/subtraction expression."""
        expr = self.factor()
        
        while self.match(TokenType.PLUS, TokenType.MINUS):
            operator_token = self.previous()
            operator = (BinaryOperator.ADD if operator_token.type == TokenType.PLUS 
                       else BinaryOperator.SUBTRACT)
            right = self.factor()
            location = expr.location
            expr = BinaryExpression(expr, operator, right, location)
        
        return expr
    
    def factor(self) -> Expression:
        """Parse multiplication/division expression."""
        expr = self.unary()
        
        while self.match(TokenType.MULTIPLY, TokenType.DIVIDE, TokenType.MODULO):
            operator_token = self.previous()
            operator_map = {
                TokenType.MULTIPLY: BinaryOperator.MULTIPLY,
                TokenType.DIVIDE: BinaryOperator.DIVIDE,
                TokenType.MODULO: BinaryOperator.MODULO,
            }
            operator = operator_map[operator_token.type]
            right = self.unary()
            location = expr.location
            expr = BinaryExpression(expr, operator, right, location)
        
        return expr
    
    def unary(self) -> Expression:
        """Parse unary expression."""
        if self.match(TokenType.NOT, TokenType.MINUS, TokenType.PLUS):
            operator_token = self.previous()
            operator_map = {
                TokenType.NOT: UnaryOperator.LOGICAL_NOT,
                TokenType.MINUS: UnaryOperator.MINUS,
                TokenType.PLUS: UnaryOperator.PLUS,
            }
            operator = operator_map[operator_token.type]
            right = self.unary()
            location = self.source_location(operator_token)
            return UnaryExpression(operator, right, location)
        
        return self.call()
    
    def call(self) -> Expression:
        """Parse function call expression."""
        expr = self.primary()
        
        while True:
            if self.match(TokenType.LPAREN):
                expr = self.finish_call(expr)
            elif self.match(TokenType.DOT):
                name = self.consume(TokenType.IDENTIFIER, 
                                  "Expected property name after '.'")
                property_id = Identifier(name.value, self.source_location(name))
                location = expr.location
                expr = MemberExpression(expr, property_id, location)
            elif self.match(TokenType.LBRACKET):
                index = self.expression()
                self.consume(TokenType.RBRACKET, "Expected ']' after index")
                location = expr.location
                expr = IndexExpression(expr, index, location)
            else:
                break
        
        return expr
    
    def finish_call(self, callee: Expression) -> CallExpression:
        """Parse function call arguments."""
        arguments = []
        
        if not self.check(TokenType.RPAREN):
            arguments.append(self.expression())
            
            while self.match(TokenType.COMMA):
                if len(arguments) >= 255:
                    raise ParseError("Can't have more than 255 arguments", self.peek())
                arguments.append(self.expression())
        
        paren = self.consume(TokenType.RPAREN, "Expected ')' after arguments")
        
        location = callee.location
        return CallExpression(callee, arguments, location)
    
    def primary(self) -> Expression:
        """Parse primary expression."""
        if self.match(TokenType.TRUE):
            token = self.previous()
            location = self.source_location(token)
            return BooleanLiteral(True, location)
        
        if self.match(TokenType.FALSE):
            token = self.previous()
            location = self.source_location(token)
            return BooleanLiteral(False, location)
        
        if self.match(TokenType.INTEGER):
            token = self.previous()
            location = self.source_location(token)
            return IntegerLiteral(int(token.value), location)
        
        if self.match(TokenType.FLOAT):
            token = self.previous()
            location = self.source_location(token)
            return FloatLiteral(float(token.value), location)
        
        if self.match(TokenType.STRING):
            token = self.previous()
            location = self.source_location(token)
            return StringLiteral(token.value, location)
        
        if self.match(TokenType.CHAR):
            token = self.previous()
            location = self.source_location(token)
            return CharLiteral(token.value, location)
        
        if self.match(TokenType.IDENTIFIER):
            token = self.previous()
            location = self.source_location(token)
            return Identifier(token.value, location)
        
        if self.match(TokenType.LPAREN):
            expr = self.expression()
            self.consume(TokenType.RPAREN, "Expected ')' after expression")
            return expr
        
        raise ParseError("Expected expression", self.peek())

def main():
    """Test the parser with sample code."""
    sample_code = '''
    fn main() {
        let x: i32 = 42;
        let mut y = 3.14;
        
        if x > 0 {
            println("Positive number");
            return x * 2;
        }
    }
    
    fn add(a: i32, b: i32) -> i32 {
        return a + b;
    }
    '''
    
    # Tokenize
    lexer = Lexer(sample_code)
    tokens = lexer.tokenize()
    
    # Parse
    parser = Parser(tokens)
    program = parser.parse()
    
    # Pretty print AST
    printer = ASTPrinter()
    print("Generated AST:")
    print(printer.visit_program(program))

if __name__ == '__main__':
    main()