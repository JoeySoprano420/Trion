"""
Parser for the Trion programming language.
Implements recursive descent parsing with error recovery for resilient parsing.
"""

from typing import List, Optional, Union
from .token import Token
from .token_types import TokenType
from .ast_nodes import *
from .errors import SyntaxError, ErrorReporter


class Parser:
    """
    Recursive descent parser for Trion with comprehensive error recovery.
    Focuses on being adaptable and resilient to syntax errors.
    """
    
    def __init__(self, tokens: List[Token], filename: Optional[str] = None):
        self.tokens = tokens
        self.filename = filename
        self.current = 0
        self.error_reporter = ErrorReporter()
    
    def is_at_end(self) -> bool:
        """Check if we're at the end of tokens."""
        return self.peek().type == TokenType.EOF
    
    def peek(self) -> Token:
        """Get current token without advancing."""
        return self.tokens[self.current]
    
    def previous(self) -> Token:
        """Get previous token."""
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
    
    def match(self, *types: TokenType) -> bool:
        """Check if current token matches any of the given types."""
        for token_type in types:
            if self.check(token_type):
                self.advance()
                return True
        return False
    
    def consume(self, token_type: TokenType, message: str) -> Token:
        """Consume token of expected type or report error."""
        if self.check(token_type):
            return self.advance()
        
        current_token = self.peek()
        self.error_reporter.syntax_error(
            message,
            current_token.line,
            current_token.column,
            self.filename
        )
        return current_token
    
    def synchronize(self):
        """Synchronize parser state after error for error recovery."""
        self.advance()
        
        while not self.is_at_end():
            if self.previous().type == TokenType.SEMICOLON:
                return
            
            if self.peek().type in {
                TokenType.CLASS,
                TokenType.FUNCTION,
                TokenType.LET,
                TokenType.CONST,
                TokenType.FOR,
                TokenType.IF,
                TokenType.WHILE,
                TokenType.RETURN,
                TokenType.TRY
            }:
                return
            
            self.advance()
    
    def parse(self) -> Optional[Program]:
        """Parse tokens into AST."""
        statements = []
        
        while not self.is_at_end():
            try:
                # Skip newlines at top level
                if self.match(TokenType.NEWLINE):
                    continue
                
                stmt = self.declaration()
                if stmt:
                    statements.append(stmt)
            except Exception as e:
                # Error recovery
                self.synchronize()
                continue
        
        if self.error_reporter.has_errors():
            return None
        
        return Program(statements)
    
    def declaration(self) -> Optional[Statement]:
        """Parse declaration."""
        try:
            if self.match(TokenType.FUNCTION):
                return self.function_declaration()
            if self.match(TokenType.CLASS):
                return self.class_declaration()
            if self.match(TokenType.LET, TokenType.CONST):
                return self.variable_declaration()
            
            return self.statement()
        except Exception:
            self.synchronize()
            return None
    
    def function_declaration(self) -> FunctionDeclaration:
        """Parse function declaration."""
        name_token = self.consume(TokenType.IDENTIFIER, "Expected function name.")
        
        self.consume(TokenType.LEFT_PAREN, "Expected '(' after function name.")
        
        parameters = []
        if not self.check(TokenType.RIGHT_PAREN):
            parameters.append(self.consume(TokenType.IDENTIFIER, "Expected parameter name.").value)
            while self.match(TokenType.COMMA):
                parameters.append(self.consume(TokenType.IDENTIFIER, "Expected parameter name.").value)
        
        self.consume(TokenType.RIGHT_PAREN, "Expected ')' after parameters.")
        
        self.consume(TokenType.LEFT_BRACE, "Expected '{' before function body.")
        body = self.block()
        
        return FunctionDeclaration(name_token.value, parameters, body, 
                                 name_token.line, name_token.column)
    
    def class_declaration(self) -> ClassDeclaration:
        """Parse class declaration."""
        name_token = self.consume(TokenType.IDENTIFIER, "Expected class name.")
        
        superclass = None
        if self.match(TokenType.COLON):
            superclass = self.consume(TokenType.IDENTIFIER, "Expected superclass name.").value
        
        self.consume(TokenType.LEFT_BRACE, "Expected '{' before class body.")
        
        methods = []
        while not self.check(TokenType.RIGHT_BRACE) and not self.is_at_end():
            if self.match(TokenType.NEWLINE):
                continue
            if self.match(TokenType.FUNCTION):
                methods.append(self.function_declaration())
            else:
                self.advance()  # Skip unknown tokens
        
        self.consume(TokenType.RIGHT_BRACE, "Expected '}' after class body.")
        
        return ClassDeclaration(name_token.value, superclass, methods,
                              name_token.line, name_token.column)
    
    def variable_declaration(self) -> VariableDeclaration:
        """Parse variable declaration."""
        is_constant = self.previous().type == TokenType.CONST
        name_token = self.consume(TokenType.IDENTIFIER, "Expected variable name.")
        
        initializer = None
        if self.match(TokenType.ASSIGN):
            initializer = self.expression()
        
        return VariableDeclaration(name_token.value, initializer, is_constant,
                                 name_token.line, name_token.column)
    
    def statement(self) -> Statement:
        """Parse statement."""
        if self.match(TokenType.IF):
            return self.if_statement()
        if self.match(TokenType.WHILE):
            return self.while_statement()
        if self.match(TokenType.FOR):
            return self.for_statement()
        if self.match(TokenType.RETURN):
            return self.return_statement()
        if self.match(TokenType.TRY):
            return self.try_statement()
        if self.match(TokenType.THROW):
            return self.throw_statement()
        if self.match(TokenType.IMPORT):
            return self.import_statement()
        if self.match(TokenType.LEFT_BRACE):
            return self.block()
        
        return self.expression_statement()
    
    def if_statement(self) -> IfStatement:
        """Parse if statement."""
        condition = self.expression()
        self.consume(TokenType.LEFT_BRACE, "Expected '{' after if condition.")
        then_branch = self.block()
        
        elif_branches = []
        while self.match(TokenType.ELIF):
            elif_condition = self.expression()
            self.consume(TokenType.LEFT_BRACE, "Expected '{' after elif condition.")
            elif_body = self.block()
            elif_branches.append((elif_condition, elif_body))
        
        else_branch = None
        if self.match(TokenType.ELSE):
            self.consume(TokenType.LEFT_BRACE, "Expected '{' after else.")
            else_branch = self.block()
        
        return IfStatement(condition, then_branch, elif_branches, else_branch)
    
    def while_statement(self) -> WhileStatement:
        """Parse while statement."""
        condition = self.expression()
        self.consume(TokenType.LEFT_BRACE, "Expected '{' after while condition.")
        body = self.block()
        
        return WhileStatement(condition, body)
    
    def for_statement(self) -> ForStatement:
        """Parse for statement."""
        variable_token = self.consume(TokenType.IDENTIFIER, "Expected variable name in for loop.")
        self.consume(TokenType.IDENTIFIER, "Expected 'in' keyword.") # TODO: Add 'in' to keywords
        iterable = self.expression()
        self.consume(TokenType.LEFT_BRACE, "Expected '{' after for clause.")
        body = self.block()
        
        return ForStatement(variable_token.value, iterable, body)
    
    def return_statement(self) -> ReturnStatement:
        """Parse return statement."""
        value = None
        if not self.check(TokenType.NEWLINE) and not self.check(TokenType.SEMICOLON):
            value = self.expression()
        
        return ReturnStatement(value)
    
    def try_statement(self) -> TryStatement:
        """Parse try statement."""
        self.consume(TokenType.LEFT_BRACE, "Expected '{' after try.")
        try_block = self.block()
        
        catch_clauses = []
        while self.match(TokenType.CATCH):
            exception_type = None
            variable = None
            
            if self.match(TokenType.LEFT_PAREN):
                exception_type = self.consume(TokenType.IDENTIFIER, "Expected exception type.").value
                if self.match(TokenType.IDENTIFIER):
                    variable = self.previous().value
                self.consume(TokenType.RIGHT_PAREN, "Expected ')' after catch clause.")
            
            self.consume(TokenType.LEFT_BRACE, "Expected '{' after catch clause.")
            catch_body = self.block()
            catch_clauses.append((exception_type, variable, catch_body))
        
        finally_block = None
        if self.match(TokenType.FINALLY):
            self.consume(TokenType.LEFT_BRACE, "Expected '{' after finally.")
            finally_block = self.block()
        
        return TryStatement(try_block, catch_clauses, finally_block)
    
    def throw_statement(self) -> ThrowStatement:
        """Parse throw statement."""
        exception = self.expression()
        return ThrowStatement(exception)
    
    def import_statement(self) -> ImportStatement:
        """Parse import statement."""
        module_token = self.consume(TokenType.IDENTIFIER, "Expected module name.")
        
        alias = None
        if self.check(TokenType.IDENTIFIER) and self.peek().value == "as":
            self.advance()  # consume 'as'
            alias = self.consume(TokenType.IDENTIFIER, "Expected alias name.").value
        
        return ImportStatement(module_token.value, alias)
    
    def block(self) -> Block:
        """Parse block statement."""
        statements = []
        
        while not self.check(TokenType.RIGHT_BRACE) and not self.is_at_end():
            if self.match(TokenType.NEWLINE):
                continue
            statements.append(self.declaration())
        
        self.consume(TokenType.RIGHT_BRACE, "Expected '}' after block.")
        return Block(statements)
    
    def expression_statement(self) -> ExpressionStatement:
        """Parse expression statement."""
        expr = self.expression()
        return ExpressionStatement(expr)
    
    def expression(self) -> Expression:
        """Parse expression."""
        return self.assignment()
    
    def assignment(self) -> Expression:
        """Parse assignment expression."""
        expr = self.logical_or()
        
        if self.match(TokenType.ASSIGN, TokenType.PLUS_ASSIGN, TokenType.MINUS_ASSIGN,
                      TokenType.MULTIPLY_ASSIGN, TokenType.DIVIDE_ASSIGN):
            operator = self.previous()
            value = self.assignment()
            
            if isinstance(expr, Identifier):
                return Assignment(expr, value, operator.line, operator.column)
            
            self.error_reporter.syntax_error("Invalid assignment target.",
                                           operator.line, operator.column, self.filename)
        
        return expr
    
    def logical_or(self) -> Expression:
        """Parse logical OR expression."""
        expr = self.logical_and()
        
        while self.match(TokenType.OR):
            operator = self.previous()
            right = self.logical_and()
            expr = BinaryOperation(expr, operator.value, right,
                                 operator.line, operator.column)
        
        return expr
    
    def logical_and(self) -> Expression:
        """Parse logical AND expression."""
        expr = self.equality()
        
        while self.match(TokenType.AND):
            operator = self.previous()
            right = self.equality()
            expr = BinaryOperation(expr, operator.value, right,
                                 operator.line, operator.column)
        
        return expr
    
    def equality(self) -> Expression:
        """Parse equality expression."""
        expr = self.comparison()
        
        while self.match(TokenType.EQUAL, TokenType.NOT_EQUAL):
            operator = self.previous()
            right = self.comparison()
            expr = BinaryOperation(expr, operator.value, right,
                                 operator.line, operator.column)
        
        return expr
    
    def comparison(self) -> Expression:
        """Parse comparison expression."""
        expr = self.term()
        
        while self.match(TokenType.GREATER_THAN, TokenType.GREATER_EQUAL,
                          TokenType.LESS_THAN, TokenType.LESS_EQUAL):
            operator = self.previous()
            right = self.term()
            expr = BinaryOperation(expr, operator.value, right,
                                 operator.line, operator.column)
        
        return expr
    
    def term(self) -> Expression:
        """Parse term expression (+ -)."""
        expr = self.factor()
        
        while self.match(TokenType.MINUS, TokenType.PLUS):
            operator = self.previous()
            right = self.factor()
            expr = BinaryOperation(expr, operator.value, right,
                                 operator.line, operator.column)
        
        return expr
    
    def factor(self) -> Expression:
        """Parse factor expression (* / %)."""
        expr = self.power()
        
        while self.match(TokenType.DIVIDE, TokenType.MULTIPLY, TokenType.MODULO):
            operator = self.previous()
            right = self.power()
            expr = BinaryOperation(expr, operator.value, right,
                                 operator.line, operator.column)
        
        return expr
    
    def power(self) -> Expression:
        """Parse power expression (**)."""
        expr = self.unary()
        
        if self.match(TokenType.POWER):
            operator = self.previous()
            right = self.power()  # Right associative
            expr = BinaryOperation(expr, operator.value, right,
                                 operator.line, operator.column)
        
        return expr
    
    def unary(self) -> Expression:
        """Parse unary expression."""
        if self.match(TokenType.NOT, TokenType.MINUS):
            operator = self.previous()
            right = self.unary()
            return UnaryOperation(operator.value, right,
                                operator.line, operator.column)
        
        return self.call()
    
    def call(self) -> Expression:
        """Parse function call expression."""
        expr = self.primary()
        
        while True:
            if self.match(TokenType.LEFT_PAREN):
                expr = self.finish_call(expr)
            elif self.match(TokenType.LEFT_BRACKET):
                index = self.expression()
                self.consume(TokenType.RIGHT_BRACKET, "Expected ']' after array index.")
                expr = ArrayAccess(expr, index)
            elif self.match(TokenType.DOT):
                name_token = self.consume(TokenType.IDENTIFIER, "Expected property name after '.'.")
                expr = MemberAccess(expr, name_token.value,
                                  name_token.line, name_token.column)
            else:
                break
        
        return expr
    
    def finish_call(self, callee: Expression) -> FunctionCall:
        """Parse function call arguments."""
        arguments = []
        
        if not self.check(TokenType.RIGHT_PAREN):
            arguments.append(self.expression())
            while self.match(TokenType.COMMA):
                arguments.append(self.expression())
        
        paren = self.consume(TokenType.RIGHT_PAREN, "Expected ')' after arguments.")
        return FunctionCall(callee, arguments, paren.line, paren.column)
    
    def primary(self) -> Expression:
        """Parse primary expression."""
        if self.match(TokenType.TRUE):
            return Literal(True, self.previous().line, self.previous().column)
        
        if self.match(TokenType.FALSE):
            return Literal(False, self.previous().line, self.previous().column)
        
        if self.match(TokenType.NULL_KW):
            return Literal(None, self.previous().line, self.previous().column)
        
        if self.match(TokenType.INTEGER):
            return Literal(int(self.previous().value),
                         self.previous().line, self.previous().column)
        
        if self.match(TokenType.FLOAT):
            return Literal(float(self.previous().value),
                         self.previous().line, self.previous().column)
        
        if self.match(TokenType.STRING):
            return Literal(self.previous().value,
                         self.previous().line, self.previous().column)
        
        if self.match(TokenType.IDENTIFIER):
            return Identifier(self.previous().value,
                            self.previous().line, self.previous().column)
        
        if self.match(TokenType.LEFT_PAREN):
            expr = self.expression()
            self.consume(TokenType.RIGHT_PAREN, "Expected ')' after expression.")
            return expr
        
        # Error recovery: create a placeholder literal
        current_token = self.peek()
        self.error_reporter.syntax_error(
            f"Unexpected token: '{current_token.value}'",
            current_token.line, current_token.column, self.filename
        )
        self.advance()  # Skip the problematic token
        return Literal(None, current_token.line, current_token.column)