"""
Trion Programming Language
A powerful, error-free, adaptable, and resilient programming language.

Version: 0.1.0
Author: Trion Development Team
"""

__version__ = "0.1.0"
__author__ = "Trion Development Team"

from .lexer import Lexer
from .parser import Parser
from .interpreter import Interpreter
from .errors import TrionError, SyntaxError, RuntimeError
from .token_types import TokenType
from .token import Token
from .ast_nodes import *

__all__ = [
    "Lexer",
    "Parser", 
    "Interpreter",
    "TrionError",
    "SyntaxError",
    "RuntimeError",
    "TokenType",
    "Token",
    "run_trion",
    "run_file"
]


def run_trion(source_code: str, filename: str = "<stdin>") -> any:
    """
    Run Trion source code.
    
    Args:
        source_code: The Trion source code to execute
        filename: Optional filename for error reporting
    
    Returns:
        The result of execution or None if there were errors
    """
    # Lexical analysis
    lexer = Lexer(source_code, filename)
    tokens = lexer.tokenize()
    
    if lexer.error_reporter.has_errors():
        lexer.error_reporter.print_errors()
        return None
    
    # Parsing
    parser = Parser(tokens, filename)
    ast = parser.parse()
    
    if parser.error_reporter.has_errors():
        parser.error_reporter.print_errors()
        return None
    
    if ast is None:
        return None
    
    # Interpretation
    interpreter = Interpreter()
    result = interpreter.interpret(ast)
    
    if interpreter.error_reporter.has_errors():
        interpreter.error_reporter.print_errors()
        return None
    
    return result


def run_file(filename: str) -> any:
    """
    Run a Trion source file.
    
    Args:
        filename: Path to the Trion source file
    
    Returns:
        The result of execution or None if there were errors
    """
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            source_code = file.read()
        return run_trion(source_code, filename)
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
        return None
    except Exception as e:
        print(f"Error reading file '{filename}': {e}")
        return None