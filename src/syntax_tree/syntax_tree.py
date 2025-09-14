#!/usr/bin/env python3
"""
Trion Language Abstract Syntax Tree (AST) Definitions

This module defines the AST node types for the Trion programming language.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Union, Any
from dataclasses import dataclass
from enum import Enum, auto

class NodeType(Enum):
    # Literals
    INTEGER_LITERAL = auto()
    FLOAT_LITERAL = auto()
    STRING_LITERAL = auto()
    CHAR_LITERAL = auto()
    BOOLEAN_LITERAL = auto()
    
    # Expressions
    IDENTIFIER = auto()
    BINARY_EXPRESSION = auto()
    UNARY_EXPRESSION = auto()
    ASSIGNMENT_EXPRESSION = auto()
    CALL_EXPRESSION = auto()
    MEMBER_EXPRESSION = auto()
    INDEX_EXPRESSION = auto()
    
    # Statements
    EXPRESSION_STATEMENT = auto()
    VARIABLE_DECLARATION = auto()
    FUNCTION_DECLARATION = auto()
    STRUCT_DECLARATION = auto()
    ENUM_DECLARATION = auto()
    IMPL_BLOCK = auto()
    
    # Control Flow
    IF_STATEMENT = auto()
    MATCH_STATEMENT = auto()
    FOR_STATEMENT = auto()
    WHILE_STATEMENT = auto()
    LOOP_STATEMENT = auto()
    BREAK_STATEMENT = auto()
    CONTINUE_STATEMENT = auto()
    RETURN_STATEMENT = auto()
    
    # Blocks
    BLOCK_STATEMENT = auto()
    
    # Program
    PROGRAM = auto()

class BinaryOperator(Enum):
    # Arithmetic
    ADD = auto()
    SUBTRACT = auto()
    MULTIPLY = auto()
    DIVIDE = auto()
    MODULO = auto()
    POWER = auto()
    
    # Comparison
    EQUAL = auto()
    NOT_EQUAL = auto()
    LESS_THAN = auto()
    LESS_EQUAL = auto()
    GREATER_THAN = auto()
    GREATER_EQUAL = auto()
    
    # Logical
    LOGICAL_AND = auto()
    LOGICAL_OR = auto()
    
    # Bitwise
    BITWISE_AND = auto()
    BITWISE_OR = auto()
    BITWISE_XOR = auto()
    LEFT_SHIFT = auto()
    RIGHT_SHIFT = auto()

class UnaryOperator(Enum):
    PLUS = auto()
    MINUS = auto()
    LOGICAL_NOT = auto()
    BITWISE_NOT = auto()

@dataclass
class SourceLocation:
    """Represents a location in the source code."""
    line: int
    column: int
    
    def __str__(self) -> str:
        return f"{self.line}:{self.column}"

class ASTNode(ABC):
    """Base class for all AST nodes."""
    
    def __init__(self, node_type: NodeType, location: SourceLocation):
        self.node_type = node_type
        self.location = location
    
    @abstractmethod
    def accept(self, visitor: 'ASTVisitor') -> Any:
        """Accept a visitor using the visitor pattern."""
        pass

class Expression(ASTNode):
    """Base class for all expressions."""
    pass

class Statement(ASTNode):
    """Base class for all statements."""
    pass

# Literal Expressions

@dataclass
class IntegerLiteral(Expression):
    value: int
    
    def __init__(self, value: int, location: SourceLocation):
        super().__init__(NodeType.INTEGER_LITERAL, location)
        self.value = value
    
    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_integer_literal(self)

@dataclass
class FloatLiteral(Expression):
    value: float
    
    def __init__(self, value: float, location: SourceLocation):
        super().__init__(NodeType.FLOAT_LITERAL, location)
        self.value = value
    
    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_float_literal(self)

@dataclass
class StringLiteral(Expression):
    value: str
    
    def __init__(self, value: str, location: SourceLocation):
        super().__init__(NodeType.STRING_LITERAL, location)
        self.value = value
    
    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_string_literal(self)

@dataclass
class CharLiteral(Expression):
    value: str
    
    def __init__(self, value: str, location: SourceLocation):
        super().__init__(NodeType.CHAR_LITERAL, location)
        self.value = value
    
    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_char_literal(self)

@dataclass
class BooleanLiteral(Expression):
    value: bool
    
    def __init__(self, value: bool, location: SourceLocation):
        super().__init__(NodeType.BOOLEAN_LITERAL, location)
        self.value = value
    
    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_boolean_literal(self)

# Identifier

@dataclass
class Identifier(Expression):
    name: str
    
    def __init__(self, name: str, location: SourceLocation):
        super().__init__(NodeType.IDENTIFIER, location)
        self.name = name
    
    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_identifier(self)

# Binary Expression

@dataclass
class BinaryExpression(Expression):
    left: Expression
    operator: BinaryOperator
    right: Expression
    
    def __init__(self, left: Expression, operator: BinaryOperator, 
                 right: Expression, location: SourceLocation):
        super().__init__(NodeType.BINARY_EXPRESSION, location)
        self.left = left
        self.operator = operator
        self.right = right
    
    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_binary_expression(self)

# Unary Expression

@dataclass
class UnaryExpression(Expression):
    operator: UnaryOperator
    operand: Expression
    
    def __init__(self, operator: UnaryOperator, operand: Expression, 
                 location: SourceLocation):
        super().__init__(NodeType.UNARY_EXPRESSION, location)
        self.operator = operator
        self.operand = operand
    
    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_unary_expression(self)

# Assignment Expression

@dataclass
class AssignmentExpression(Expression):
    target: Expression
    value: Expression
    
    def __init__(self, target: Expression, value: Expression, 
                 location: SourceLocation):
        super().__init__(NodeType.ASSIGNMENT_EXPRESSION, location)
        self.target = target
        self.value = value
    
    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_assignment_expression(self)

# Call Expression

@dataclass
class CallExpression(Expression):
    callee: Expression
    arguments: List[Expression]
    
    def __init__(self, callee: Expression, arguments: List[Expression], 
                 location: SourceLocation):
        super().__init__(NodeType.CALL_EXPRESSION, location)
        self.callee = callee
        self.arguments = arguments
    
    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_call_expression(self)

# Member Expression (dot notation)

@dataclass
class MemberExpression(Expression):
    object: Expression
    property: Identifier
    
    def __init__(self, object: Expression, property: Identifier, 
                 location: SourceLocation):
        super().__init__(NodeType.MEMBER_EXPRESSION, location)
        self.object = object
        self.property = property
    
    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_member_expression(self)

# Index Expression (array/map access)

@dataclass
class IndexExpression(Expression):
    object: Expression
    index: Expression
    
    def __init__(self, object: Expression, index: Expression, 
                 location: SourceLocation):
        super().__init__(NodeType.INDEX_EXPRESSION, location)
        self.object = object
        self.index = index
    
    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_index_expression(self)

# Type Annotations

@dataclass
class TypeAnnotation:
    name: str
    generics: Optional[List['TypeAnnotation']] = None
    
    def __str__(self) -> str:
        if self.generics:
            generic_str = ', '.join(str(g) for g in self.generics)
            return f"{self.name}<{generic_str}>"
        return self.name

# Function Parameter

@dataclass
class Parameter:
    name: str
    type_annotation: Optional[TypeAnnotation]
    
    def __str__(self) -> str:
        if self.type_annotation:
            return f"{self.name}: {self.type_annotation}"
        return self.name

# Statements

@dataclass
class ExpressionStatement(Statement):
    expression: Expression
    
    def __init__(self, expression: Expression, location: SourceLocation):
        super().__init__(NodeType.EXPRESSION_STATEMENT, location)
        self.expression = expression
    
    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_expression_statement(self)

@dataclass
class VariableDeclaration(Statement):
    name: str
    type_annotation: Optional[TypeAnnotation]
    initializer: Optional[Expression]
    is_mutable: bool
    
    def __init__(self, name: str, type_annotation: Optional[TypeAnnotation], 
                 initializer: Optional[Expression], is_mutable: bool, 
                 location: SourceLocation):
        super().__init__(NodeType.VARIABLE_DECLARATION, location)
        self.name = name
        self.type_annotation = type_annotation
        self.initializer = initializer
        self.is_mutable = is_mutable
    
    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_variable_declaration(self)

@dataclass
class FunctionDeclaration(Statement):
    name: str
    parameters: List[Parameter]
    return_type: Optional[TypeAnnotation]
    body: 'BlockStatement'
    is_async: bool = False
    
    def __init__(self, name: str, parameters: List[Parameter], 
                 return_type: Optional[TypeAnnotation], body: 'BlockStatement',
                 is_async: bool, location: SourceLocation):
        super().__init__(NodeType.FUNCTION_DECLARATION, location)
        self.name = name
        self.parameters = parameters
        self.return_type = return_type
        self.body = body
        self.is_async = is_async
    
    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_function_declaration(self)

@dataclass
class BlockStatement(Statement):
    statements: List[Statement]
    
    def __init__(self, statements: List[Statement], location: SourceLocation):
        super().__init__(NodeType.BLOCK_STATEMENT, location)
        self.statements = statements
    
    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_block_statement(self)

@dataclass
class IfStatement(Statement):
    condition: Expression
    then_branch: Statement
    else_branch: Optional[Statement]
    
    def __init__(self, condition: Expression, then_branch: Statement, 
                 else_branch: Optional[Statement], location: SourceLocation):
        super().__init__(NodeType.IF_STATEMENT, location)
        self.condition = condition
        self.then_branch = then_branch
        self.else_branch = else_branch
    
    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_if_statement(self)

@dataclass
class WhileStatement(Statement):
    condition: Expression
    body: Statement
    
    def __init__(self, condition: Expression, body: Statement, 
                 location: SourceLocation):
        super().__init__(NodeType.WHILE_STATEMENT, location)
        self.condition = condition
        self.body = body
    
    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_while_statement(self)

@dataclass
class ReturnStatement(Statement):
    value: Optional[Expression]
    
    def __init__(self, value: Optional[Expression], location: SourceLocation):
        super().__init__(NodeType.RETURN_STATEMENT, location)
        self.value = value
    
    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_return_statement(self)

@dataclass
class BreakStatement(Statement):
    def __init__(self, location: SourceLocation):
        super().__init__(NodeType.BREAK_STATEMENT, location)
    
    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_break_statement(self)

@dataclass
class ContinueStatement(Statement):
    def __init__(self, location: SourceLocation):
        super().__init__(NodeType.CONTINUE_STATEMENT, location)
    
    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_continue_statement(self)

# Program (root node)

@dataclass
class Program(ASTNode):
    statements: List[Statement]
    
    def __init__(self, statements: List[Statement], location: SourceLocation):
        super().__init__(NodeType.PROGRAM, location)
        self.statements = statements
    
    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_program(self)

# Visitor Pattern

class ASTVisitor(ABC):
    """Base class for AST visitors."""
    
    @abstractmethod
    def visit_integer_literal(self, node: IntegerLiteral) -> Any:
        pass
    
    @abstractmethod
    def visit_float_literal(self, node: FloatLiteral) -> Any:
        pass
    
    @abstractmethod
    def visit_string_literal(self, node: StringLiteral) -> Any:
        pass
    
    @abstractmethod
    def visit_char_literal(self, node: CharLiteral) -> Any:
        pass
    
    @abstractmethod
    def visit_boolean_literal(self, node: BooleanLiteral) -> Any:
        pass
    
    @abstractmethod
    def visit_identifier(self, node: Identifier) -> Any:
        pass
    
    @abstractmethod
    def visit_binary_expression(self, node: BinaryExpression) -> Any:
        pass
    
    @abstractmethod
    def visit_unary_expression(self, node: UnaryExpression) -> Any:
        pass
    
    @abstractmethod
    def visit_assignment_expression(self, node: AssignmentExpression) -> Any:
        pass
    
    @abstractmethod
    def visit_call_expression(self, node: CallExpression) -> Any:
        pass
    
    @abstractmethod
    def visit_member_expression(self, node: MemberExpression) -> Any:
        pass
    
    @abstractmethod
    def visit_index_expression(self, node: IndexExpression) -> Any:
        pass
    
    @abstractmethod
    def visit_expression_statement(self, node: ExpressionStatement) -> Any:
        pass
    
    @abstractmethod
    def visit_variable_declaration(self, node: VariableDeclaration) -> Any:
        pass
    
    @abstractmethod
    def visit_function_declaration(self, node: FunctionDeclaration) -> Any:
        pass
    
    @abstractmethod
    def visit_block_statement(self, node: BlockStatement) -> Any:
        pass
    
    @abstractmethod
    def visit_if_statement(self, node: IfStatement) -> Any:
        pass
    
    @abstractmethod
    def visit_while_statement(self, node: WhileStatement) -> Any:
        pass
    
    @abstractmethod
    def visit_return_statement(self, node: ReturnStatement) -> Any:
        pass
    
    @abstractmethod
    def visit_break_statement(self, node: BreakStatement) -> Any:
        pass
    
    @abstractmethod
    def visit_continue_statement(self, node: ContinueStatement) -> Any:
        pass
    
    @abstractmethod
    def visit_program(self, node: Program) -> Any:
        pass

# Pretty Printer for AST

class ASTPrinter(ASTVisitor):
    """Prints AST in a human-readable format."""
    
    def __init__(self, indent_size: int = 2):
        self.indent_size = indent_size
        self.current_indent = 0
    
    def _indent(self) -> str:
        return ' ' * (self.current_indent * self.indent_size)
    
    def _print_with_indent(self, text: str) -> str:
        return f"{self._indent()}{text}"
    
    def visit_integer_literal(self, node: IntegerLiteral) -> str:
        return str(node.value)
    
    def visit_float_literal(self, node: FloatLiteral) -> str:
        return str(node.value)
    
    def visit_string_literal(self, node: StringLiteral) -> str:
        return f'"{node.value}"'
    
    def visit_char_literal(self, node: CharLiteral) -> str:
        return f"'{node.value}'"
    
    def visit_boolean_literal(self, node: BooleanLiteral) -> str:
        return "true" if node.value else "false"
    
    def visit_identifier(self, node: Identifier) -> str:
        return node.name
    
    def visit_binary_expression(self, node: BinaryExpression) -> str:
        left = node.left.accept(self)
        right = node.right.accept(self)
        op_map = {
            BinaryOperator.ADD: '+',
            BinaryOperator.SUBTRACT: '-',
            BinaryOperator.MULTIPLY: '*',
            BinaryOperator.DIVIDE: '/',
            BinaryOperator.EQUAL: '==',
            BinaryOperator.NOT_EQUAL: '!=',
            BinaryOperator.LESS_THAN: '<',
            BinaryOperator.GREATER_THAN: '>',
        }
        op = op_map.get(node.operator, str(node.operator))
        return f"({left} {op} {right})"
    
    def visit_unary_expression(self, node: UnaryExpression) -> str:
        operand = node.operand.accept(self)
        op_map = {
            UnaryOperator.MINUS: '-',
            UnaryOperator.PLUS: '+',
            UnaryOperator.LOGICAL_NOT: '!',
        }
        op = op_map.get(node.operator, str(node.operator))
        return f"{op}{operand}"
    
    def visit_assignment_expression(self, node: AssignmentExpression) -> str:
        target = node.target.accept(self)
        value = node.value.accept(self)
        return f"{target} = {value}"
    
    def visit_call_expression(self, node: CallExpression) -> str:
        callee = node.callee.accept(self)
        args = [arg.accept(self) for arg in node.arguments]
        return f"{callee}({', '.join(args)})"
    
    def visit_member_expression(self, node: MemberExpression) -> str:
        obj = node.object.accept(self)
        prop = node.property.accept(self)
        return f"{obj}.{prop}"
    
    def visit_index_expression(self, node: IndexExpression) -> str:
        obj = node.object.accept(self)
        idx = node.index.accept(self)
        return f"{obj}[{idx}]"
    
    def visit_expression_statement(self, node: ExpressionStatement) -> str:
        expr = node.expression.accept(self)
        return self._print_with_indent(f"{expr};")
    
    def visit_variable_declaration(self, node: VariableDeclaration) -> str:
        mut_str = "mut " if node.is_mutable else ""
        type_str = f": {node.type_annotation}" if node.type_annotation else ""
        init_str = f" = {node.initializer.accept(self)}" if node.initializer else ""
        return self._print_with_indent(f"let {mut_str}{node.name}{type_str}{init_str};")
    
    def visit_function_declaration(self, node: FunctionDeclaration) -> str:
        async_str = "async " if node.is_async else ""
        params = [f"{p.name}: {p.type_annotation}" for p in node.parameters]
        return_str = f" -> {node.return_type}" if node.return_type else ""
        
        result = self._print_with_indent(f"{async_str}fn {node.name}({', '.join(params)}){return_str} ")
        result += "{\n"
        
        self.current_indent += 1
        body = node.body.accept(self)
        self.current_indent -= 1
        
        result += body + "\n"
        result += self._print_with_indent("}")
        return result
    
    def visit_block_statement(self, node: BlockStatement) -> str:
        result = ""
        for stmt in node.statements:
            result += stmt.accept(self) + "\n"
        return result.rstrip()
    
    def visit_if_statement(self, node: IfStatement) -> str:
        condition = node.condition.accept(self)
        result = self._print_with_indent(f"if {condition} ")
        
        if isinstance(node.then_branch, BlockStatement):
            result += "{\n"
            self.current_indent += 1
            result += node.then_branch.accept(self) + "\n"
            self.current_indent -= 1
            result += self._print_with_indent("}")
        else:
            result += "\n"
            self.current_indent += 1
            result += node.then_branch.accept(self)
            self.current_indent -= 1
        
        if node.else_branch:
            result += " else "
            if isinstance(node.else_branch, BlockStatement):
                result += "{\n"
                self.current_indent += 1
                result += node.else_branch.accept(self) + "\n"
                self.current_indent -= 1
                result += self._print_with_indent("}")
            else:
                result += "\n"
                self.current_indent += 1
                result += node.else_branch.accept(self)
                self.current_indent -= 1
        
        return result
    
    def visit_while_statement(self, node: WhileStatement) -> str:
        condition = node.condition.accept(self)
        result = self._print_with_indent(f"while {condition} ")
        
        if isinstance(node.body, BlockStatement):
            result += "{\n"
            self.current_indent += 1
            result += node.body.accept(self) + "\n"
            self.current_indent -= 1
            result += self._print_with_indent("}")
        else:
            result += "\n"
            self.current_indent += 1
            result += node.body.accept(self)
            self.current_indent -= 1
        
        return result
    
    def visit_return_statement(self, node: ReturnStatement) -> str:
        if node.value:
            value = node.value.accept(self)
            return self._print_with_indent(f"return {value};")
        return self._print_with_indent("return;")
    
    def visit_break_statement(self, node: BreakStatement) -> str:
        return self._print_with_indent("break;")
    
    def visit_continue_statement(self, node: ContinueStatement) -> str:
        return self._print_with_indent("continue;")
    
    def visit_program(self, node: Program) -> str:
        result = ""
        for stmt in node.statements:
            result += stmt.accept(self) + "\n\n"
        return result.rstrip()