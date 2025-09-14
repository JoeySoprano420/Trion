"""
Interpreter for the Trion programming language.
Executes AST nodes with comprehensive error handling and type safety.
"""

from typing import Any, Dict, List, Optional
from .ast_nodes import *
from .errors import RuntimeError, NameError, TypeError, ValueError, ErrorReporter


class Environment:
    """Environment for variable storage with scope management."""
    
    def __init__(self, enclosing: Optional['Environment'] = None):
        self.values: Dict[str, Any] = {}
        self.constants: set = set()
        self.enclosing = enclosing
    
    def define(self, name: str, value: Any, is_constant: bool = False):
        """Define a new variable."""
        self.values[name] = value
        if is_constant:
            self.constants.add(name)
    
    def get(self, name: str) -> Any:
        """Get variable value."""
        if name in self.values:
            return self.values[name]
        
        if self.enclosing:
            return self.enclosing.get(name)
        
        raise NameError(f"Undefined variable '{name}'.")
    
    def assign(self, name: str, value: Any):
        """Assign value to existing variable."""
        if name in self.values:
            if name in self.constants:
                raise RuntimeError(f"Cannot assign to constant '{name}'.")
            self.values[name] = value
            return
        
        if self.enclosing:
            self.enclosing.assign(name, value)
            return
        
        raise NameError(f"Undefined variable '{name}'.")


class TrionFunction:
    """Represents a Trion function."""
    
    def __init__(self, declaration: FunctionDeclaration, closure: Environment):
        self.declaration = declaration
        self.closure = closure
    
    def call(self, interpreter: 'Interpreter', arguments: List[Any]) -> Any:
        """Call the function with given arguments."""
        if len(arguments) != len(self.declaration.parameters):
            raise RuntimeError(f"Expected {len(self.declaration.parameters)} arguments "
                             f"but got {len(arguments)}.")
        
        # Create new environment for function execution
        environment = Environment(self.closure)
        
        # Bind parameters
        for i, param in enumerate(self.declaration.parameters):
            environment.define(param, arguments[i])
        
        try:
            interpreter.execute_block(self.declaration.body.statements, environment)
        except ReturnException as return_value:
            return return_value.value
        
        return None  # Implicit return None


class ReturnException(Exception):
    """Exception used to handle return statements."""
    
    def __init__(self, value: Any):
        self.value = value


class Interpreter(ASTVisitor):
    """
    Interpreter for Trion AST with robust error handling.
    Focuses on being powerful, error-free, adaptable, and resilient.
    """
    
    def __init__(self):
        self.globals = Environment()
        self.environment = self.globals
        self.error_reporter = ErrorReporter()
        
        # Built-in functions
        self._define_builtins()
    
    def _define_builtins(self):
        """Define built-in functions."""
        def builtin_print(*args):
            print(*args)
            return None
        
        def builtin_len(obj):
            if hasattr(obj, '__len__'):
                return len(obj)
            raise TypeError(f"Object of type '{type(obj).__name__}' has no len()")
        
        def builtin_type(obj):
            return type(obj).__name__
        
        def builtin_str(obj):
            return str(obj)
        
        def builtin_int(obj):
            try:
                return int(obj)
            except ValueError:
                raise ValueError(f"Cannot convert '{obj}' to int")
        
        def builtin_float(obj):
            try:
                return float(obj)
            except ValueError:
                raise ValueError(f"Cannot convert '{obj}' to float")
        
        self.globals.define("print", builtin_print)
        self.globals.define("len", builtin_len)
        self.globals.define("type", builtin_type)
        self.globals.define("str", builtin_str)
        self.globals.define("int", builtin_int)
        self.globals.define("float", builtin_float)
    
    def interpret(self, program: Program) -> Any:
        """Interpret the program."""
        try:
            return self.visit_program(program)
        except Exception as e:
            if isinstance(e, (RuntimeError, NameError, TypeError, ValueError)):
                self.error_reporter.runtime_error(str(e))
            else:
                self.error_reporter.runtime_error(f"Unexpected error: {e}")
            return None
    
    def visit_program(self, node: Program) -> Any:
        """Visit program node."""
        last_value = None
        for statement in node.statements:
            last_value = statement.accept(self)
        return last_value
    
    def visit_literal(self, node: Literal) -> Any:
        """Visit literal node."""
        return node.value
    
    def visit_identifier(self, node: Identifier) -> Any:
        """Visit identifier node."""
        try:
            return self.environment.get(node.name)
        except NameError as e:
            raise NameError(str(e), node.line, node.column)
    
    def visit_binary_operation(self, node: BinaryOperation) -> Any:
        """Visit binary operation node."""
        left = node.left.accept(self)
        right = node.right.accept(self)
        
        try:
            if node.operator == '+':
                return left + right
            elif node.operator == '-':
                return left - right
            elif node.operator == '*':
                return left * right
            elif node.operator == '/':
                if right == 0:
                    raise ValueError("Division by zero")
                return left / right
            elif node.operator == '%':
                if right == 0:
                    raise ValueError("Modulo by zero")
                return left % right
            elif node.operator == '**':
                return left ** right
            elif node.operator == '==':
                return left == right
            elif node.operator == '!=':
                return left != right
            elif node.operator == '<':
                return left < right
            elif node.operator == '<=':
                return left <= right
            elif node.operator == '>':
                return left > right
            elif node.operator == '>=':
                return left >= right
            elif node.operator == 'and':
                return left and right
            elif node.operator == 'or':
                return left or right
            else:
                raise RuntimeError(f"Unknown binary operator: {node.operator}")
        except (TypeError, ValueError) as e:
            raise RuntimeError(str(e), node.line, node.column)
    
    def visit_unary_operation(self, node: UnaryOperation) -> Any:
        """Visit unary operation node."""
        operand = node.operand.accept(self)
        
        try:
            if node.operator == '-':
                return -operand
            elif node.operator == 'not':
                return not operand
            else:
                raise RuntimeError(f"Unknown unary operator: {node.operator}")
        except TypeError as e:
            raise RuntimeError(str(e), node.line, node.column)
    
    def visit_assignment(self, node: Assignment) -> Any:
        """Visit assignment node."""
        value = node.value.accept(self)
        
        try:
            self.environment.assign(node.target.name, value)
        except (NameError, RuntimeError) as e:
            raise RuntimeError(str(e), node.line, node.column)
        
        return value
    
    def visit_function_call(self, node: FunctionCall) -> Any:
        """Visit function call node."""
        function = node.function.accept(self)
        
        arguments = []
        for arg in node.arguments:
            arguments.append(arg.accept(self))
        
        try:
            if isinstance(function, TrionFunction):
                return function.call(self, arguments)
            elif callable(function):
                return function(*arguments)
            else:
                raise TypeError(f"'{type(function).__name__}' object is not callable")
        except Exception as e:
            raise RuntimeError(f"Error calling function: {e}", node.line, node.column)
    
    def visit_array_access(self, node: ArrayAccess) -> Any:
        """Visit array access node."""
        array = node.array.accept(self)
        index = node.index.accept(self)
        
        try:
            return array[index]
        except (IndexError, KeyError, TypeError) as e:
            raise RuntimeError(str(e), node.line, node.column)
    
    def visit_member_access(self, node: MemberAccess) -> Any:
        """Visit member access node."""
        obj = node.object.accept(self)
        
        try:
            return getattr(obj, node.member)
        except AttributeError:
            raise RuntimeError(f"'{type(obj).__name__}' object has no attribute '{node.member}'",
                             node.line, node.column)
    
    def visit_expression_statement(self, node: ExpressionStatement) -> Any:
        """Visit expression statement node."""
        return node.expression.accept(self)
    
    def visit_block(self, node: Block) -> Any:
        """Visit block node."""
        return self.execute_block(node.statements, Environment(self.environment))
    
    def execute_block(self, statements: List[Statement], environment: Environment) -> Any:
        """Execute block of statements in given environment."""
        previous = self.environment
        try:
            self.environment = environment
            
            last_value = None
            for statement in statements:
                if statement:  # Skip None statements (from error recovery)
                    last_value = statement.accept(self)
            
            return last_value
        finally:
            self.environment = previous
    
    def visit_variable_declaration(self, node: VariableDeclaration) -> Any:
        """Visit variable declaration node."""
        value = None
        if node.initializer:
            value = node.initializer.accept(self)
        
        self.environment.define(node.name, value, node.is_constant)
        return value
    
    def visit_if_statement(self, node: IfStatement) -> Any:
        """Visit if statement node."""
        condition = node.condition.accept(self)
        
        if self.is_truthy(condition):
            return node.then_branch.accept(self)
        
        # Check elif branches
        for elif_condition, elif_body in node.elif_branches:
            if self.is_truthy(elif_condition.accept(self)):
                return elif_body.accept(self)
        
        # Execute else branch if present
        if node.else_branch:
            return node.else_branch.accept(self)
        
        return None
    
    def visit_while_statement(self, node: WhileStatement) -> Any:
        """Visit while statement node."""
        last_value = None
        while self.is_truthy(node.condition.accept(self)):
            last_value = node.body.accept(self)
        return last_value
    
    def visit_for_statement(self, node: ForStatement) -> Any:
        """Visit for statement node."""
        iterable = node.iterable.accept(self)
        
        try:
            last_value = None
            for item in iterable:
                # Create new scope for loop variable
                loop_env = Environment(self.environment)
                loop_env.define(node.variable, item)
                
                previous = self.environment
                try:
                    self.environment = loop_env
                    last_value = node.body.accept(self)
                finally:
                    self.environment = previous
            
            return last_value
        except TypeError:
            raise RuntimeError(f"'{type(iterable).__name__}' object is not iterable",
                             node.line, node.column)
    
    def visit_return_statement(self, node: ReturnStatement) -> Any:
        """Visit return statement node."""
        value = None
        if node.value:
            value = node.value.accept(self)
        
        raise ReturnException(value)
    
    def visit_function_declaration(self, node: FunctionDeclaration) -> Any:
        """Visit function declaration node."""
        function = TrionFunction(node, self.environment)
        self.environment.define(node.name, function)
        return function
    
    def visit_class_declaration(self, node: ClassDeclaration) -> Any:
        """Visit class declaration node (basic implementation)."""
        # This is a simplified class implementation
        class_methods = {}
        
        for method in node.methods:
            class_methods[method.name] = TrionFunction(method, self.environment)
        
        self.environment.define(node.name, class_methods)
        return class_methods
    
    def visit_try_statement(self, node: TryStatement) -> Any:
        """Visit try statement node."""
        result = None
        exception_occurred = False
        
        try:
            result = node.try_block.accept(self)
        except ReturnException:
            # Re-raise return exceptions, don't catch them
            raise
        except Exception as e:
            exception_occurred = True
            # Simple exception handling - match any catch block
            for exception_type, variable, catch_body in node.catch_clauses:
                if variable:
                    catch_env = Environment(self.environment)
                    catch_env.define(variable, e)
                    result = self.execute_block(catch_body.statements, catch_env)
                else:
                    result = catch_body.accept(self)
                break  # Only execute the first matching catch block
        finally:
            if node.finally_block:
                node.finally_block.accept(self)
        
        return result
    
    def visit_throw_statement(self, node: ThrowStatement) -> Any:
        """Visit throw statement node."""
        exception = node.exception.accept(self)
        raise RuntimeError(str(exception), node.line, node.column)
    
    def visit_import_statement(self, node: ImportStatement) -> Any:
        """Visit import statement node (basic implementation)."""
        # This is a placeholder - real implementation would load modules
        self.environment.define(node.module, f"Module: {node.module}")
        return None
    
    def is_truthy(self, value: Any) -> bool:
        """Determine truthiness of value."""
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return len(value) > 0
        if hasattr(value, '__len__'):
            return len(value) > 0
        return True