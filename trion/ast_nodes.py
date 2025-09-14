"""
Abstract Syntax Tree (AST) definitions for Trion programming language.
Provides robust node structure for representing parsed code.
"""

from abc import ABC, abstractmethod
from typing import Any, List, Optional, Union


class ASTNode(ABC):
    """Base class for all AST nodes."""
    
    def __init__(self, line: int = 0, column: int = 0):
        self.line = line
        self.column = column
    
    @abstractmethod
    def accept(self, visitor):
        """Accept visitor for visitor pattern implementation."""
        pass


# Expression nodes
class Expression(ASTNode):
    """Base class for all expressions."""
    pass


class Literal(Expression):
    """Literal value expression."""
    
    def __init__(self, value: Any, line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.value = value
    
    def accept(self, visitor):
        return visitor.visit_literal(self)


class Identifier(Expression):
    """Identifier expression."""
    
    def __init__(self, name: str, line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.name = name
    
    def accept(self, visitor):
        return visitor.visit_identifier(self)


class BinaryOperation(Expression):
    """Binary operation expression."""
    
    def __init__(self, left: Expression, operator: str, right: Expression, 
                 line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.left = left
        self.operator = operator
        self.right = right
    
    def accept(self, visitor):
        return visitor.visit_binary_operation(self)


class UnaryOperation(Expression):
    """Unary operation expression."""
    
    def __init__(self, operator: str, operand: Expression, line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.operator = operator
        self.operand = operand
    
    def accept(self, visitor):
        return visitor.visit_unary_operation(self)


class Assignment(Expression):
    """Assignment expression."""
    
    def __init__(self, target: Identifier, value: Expression, 
                 line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.target = target
        self.value = value
    
    def accept(self, visitor):
        return visitor.visit_assignment(self)


class FunctionCall(Expression):
    """Function call expression."""
    
    def __init__(self, function: Expression, arguments: List[Expression], 
                 line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.function = function
        self.arguments = arguments
    
    def accept(self, visitor):
        return visitor.visit_function_call(self)


class ArrayAccess(Expression):
    """Array access expression."""
    
    def __init__(self, array: Expression, index: Expression, 
                 line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.array = array
        self.index = index
    
    def accept(self, visitor):
        return visitor.visit_array_access(self)


class MemberAccess(Expression):
    """Member access expression (obj.member)."""
    
    def __init__(self, object_expr: Expression, member: str, 
                 line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.object = object_expr
        self.member = member
    
    def accept(self, visitor):
        return visitor.visit_member_access(self)


# Statement nodes
class Statement(ASTNode):
    """Base class for all statements."""
    pass


class ExpressionStatement(Statement):
    """Expression used as a statement."""
    
    def __init__(self, expression: Expression, line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.expression = expression
    
    def accept(self, visitor):
        return visitor.visit_expression_statement(self)


class Block(Statement):
    """Block of statements."""
    
    def __init__(self, statements: List[Statement], line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.statements = statements
    
    def accept(self, visitor):
        return visitor.visit_block(self)


class VariableDeclaration(Statement):
    """Variable declaration statement."""
    
    def __init__(self, name: str, initializer: Optional[Expression] = None, 
                 is_constant: bool = False, line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.name = name
        self.initializer = initializer
        self.is_constant = is_constant
    
    def accept(self, visitor):
        return visitor.visit_variable_declaration(self)


class IfStatement(Statement):
    """If statement with optional elif and else clauses."""
    
    def __init__(self, condition: Expression, then_branch: Statement,
                 elif_branches: Optional[List[tuple]] = None,
                 else_branch: Optional[Statement] = None,
                 line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.condition = condition
        self.then_branch = then_branch
        self.elif_branches = elif_branches or []  # List of (condition, statement) tuples
        self.else_branch = else_branch
    
    def accept(self, visitor):
        return visitor.visit_if_statement(self)


class WhileStatement(Statement):
    """While loop statement."""
    
    def __init__(self, condition: Expression, body: Statement, 
                 line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.condition = condition
        self.body = body
    
    def accept(self, visitor):
        return visitor.visit_while_statement(self)


class ForStatement(Statement):
    """For loop statement."""
    
    def __init__(self, variable: str, iterable: Expression, body: Statement,
                 line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.variable = variable
        self.iterable = iterable
        self.body = body
    
    def accept(self, visitor):
        return visitor.visit_for_statement(self)


class ReturnStatement(Statement):
    """Return statement."""
    
    def __init__(self, value: Optional[Expression] = None, 
                 line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.value = value
    
    def accept(self, visitor):
        return visitor.visit_return_statement(self)


class FunctionDeclaration(Statement):
    """Function declaration statement."""
    
    def __init__(self, name: str, parameters: List[str], body: Block,
                 line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.name = name
        self.parameters = parameters
        self.body = body
    
    def accept(self, visitor):
        return visitor.visit_function_declaration(self)


class ClassDeclaration(Statement):
    """Class declaration statement."""
    
    def __init__(self, name: str, superclass: Optional[str], methods: List[FunctionDeclaration],
                 line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.name = name
        self.superclass = superclass
        self.methods = methods
    
    def accept(self, visitor):
        return visitor.visit_class_declaration(self)


class TryStatement(Statement):
    """Try-catch-finally statement."""
    
    def __init__(self, try_block: Block, 
                 catch_clauses: List[tuple], # (exception_type, variable, block)
                 finally_block: Optional[Block] = None,
                 line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.try_block = try_block
        self.catch_clauses = catch_clauses
        self.finally_block = finally_block
    
    def accept(self, visitor):
        return visitor.visit_try_statement(self)


class ThrowStatement(Statement):
    """Throw statement."""
    
    def __init__(self, exception: Expression, line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.exception = exception
    
    def accept(self, visitor):
        return visitor.visit_throw_statement(self)


class ImportStatement(Statement):
    """Import statement."""
    
    def __init__(self, module: str, alias: Optional[str] = None,
                 items: Optional[List[str]] = None,
                 line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.module = module
        self.alias = alias
        self.items = items  # For 'from module import item1, item2'
    
    def accept(self, visitor):
        return visitor.visit_import_statement(self)


# Program node
class Program(ASTNode):
    """Root program node containing all statements."""
    
    def __init__(self, statements: List[Statement]):
        super().__init__()
        self.statements = statements
    
    def accept(self, visitor):
        return visitor.visit_program(self)


# Visitor interface for AST traversal
class ASTVisitor(ABC):
    """Abstract visitor for AST traversal."""
    
    @abstractmethod
    def visit_literal(self, node: Literal): pass
    
    @abstractmethod
    def visit_identifier(self, node: Identifier): pass
    
    @abstractmethod
    def visit_binary_operation(self, node: BinaryOperation): pass
    
    @abstractmethod
    def visit_unary_operation(self, node: UnaryOperation): pass
    
    @abstractmethod
    def visit_assignment(self, node: Assignment): pass
    
    @abstractmethod
    def visit_function_call(self, node: FunctionCall): pass
    
    @abstractmethod
    def visit_array_access(self, node: ArrayAccess): pass
    
    @abstractmethod
    def visit_member_access(self, node: MemberAccess): pass
    
    @abstractmethod
    def visit_expression_statement(self, node: ExpressionStatement): pass
    
    @abstractmethod
    def visit_block(self, node: Block): pass
    
    @abstractmethod
    def visit_variable_declaration(self, node: VariableDeclaration): pass
    
    @abstractmethod
    def visit_if_statement(self, node: IfStatement): pass
    
    @abstractmethod
    def visit_while_statement(self, node: WhileStatement): pass
    
    @abstractmethod
    def visit_for_statement(self, node: ForStatement): pass
    
    @abstractmethod
    def visit_return_statement(self, node: ReturnStatement): pass
    
    @abstractmethod
    def visit_function_declaration(self, node: FunctionDeclaration): pass
    
    @abstractmethod
    def visit_class_declaration(self, node: ClassDeclaration): pass
    
    @abstractmethod
    def visit_try_statement(self, node: TryStatement): pass
    
    @abstractmethod
    def visit_throw_statement(self, node: ThrowStatement): pass
    
    @abstractmethod
    def visit_import_statement(self, node: ImportStatement): pass
    
    @abstractmethod
    def visit_program(self, node: Program): pass