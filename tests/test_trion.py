"""
Test suite for Trion programming language.
Validates lexer, parser, and interpreter functionality.
"""

import unittest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import trion
from trion.lexer import Lexer
from trion.parser import Parser
from trion.interpreter import Interpreter
from trion.token_types import TokenType


class TestTrionLexer(unittest.TestCase):
    """Test the Trion lexer."""
    
    def test_basic_tokens(self):
        """Test basic token recognition."""
        source = "let x = 42"
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        
        expected_types = [
            TokenType.LET,
            TokenType.IDENTIFIER,
            TokenType.ASSIGN,
            TokenType.INTEGER,
            TokenType.EOF
        ]
        
        self.assertEqual(len(tokens), len(expected_types))
        for i, expected_type in enumerate(expected_types):
            self.assertEqual(tokens[i].type, expected_type)
    
    def test_string_literals(self):
        """Test string literal tokenization."""
        source = '"Hello, World!"'
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        
        self.assertEqual(tokens[0].type, TokenType.STRING)
        self.assertEqual(tokens[0].value, "Hello, World!")
    
    def test_numbers(self):
        """Test number tokenization."""
        source = "42 3.14 2e5"
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        
        self.assertEqual(tokens[0].type, TokenType.INTEGER)
        self.assertEqual(tokens[0].value, "42")
        
        self.assertEqual(tokens[1].type, TokenType.FLOAT)
        self.assertEqual(tokens[1].value, "3.14")
        
        self.assertEqual(tokens[2].type, TokenType.FLOAT)
        self.assertEqual(tokens[2].value, "2e5")
    
    def test_operators(self):
        """Test operator tokenization."""
        source = "+ - * / % ** == != < <= > >="
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        
        expected_types = [
            TokenType.PLUS, TokenType.MINUS, TokenType.MULTIPLY,
            TokenType.DIVIDE, TokenType.MODULO, TokenType.POWER,
            TokenType.EQUAL, TokenType.NOT_EQUAL,
            TokenType.LESS_THAN, TokenType.LESS_EQUAL,
            TokenType.GREATER_THAN, TokenType.GREATER_EQUAL,
            TokenType.EOF
        ]
        
        for i, expected_type in enumerate(expected_types):
            self.assertEqual(tokens[i].type, expected_type)


class TestTrionParser(unittest.TestCase):
    """Test the Trion parser."""
    
    def parse_expression(self, source):
        """Helper to parse a simple expression."""
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        return parser.expression()
    
    def test_literal_parsing(self):
        """Test literal expression parsing."""
        expr = self.parse_expression("42")
        self.assertIsInstance(expr, trion.Literal)
        self.assertEqual(expr.value, 42)
    
    def test_binary_operations(self):
        """Test binary operation parsing."""
        expr = self.parse_expression("1 + 2")
        self.assertIsInstance(expr, trion.BinaryOperation)
        self.assertEqual(expr.operator, "+")
    
    def test_precedence(self):
        """Test operator precedence."""
        expr = self.parse_expression("1 + 2 * 3")
        self.assertIsInstance(expr, trion.BinaryOperation)
        self.assertEqual(expr.operator, "+")
        
        # Right side should be multiplication
        self.assertIsInstance(expr.right, trion.BinaryOperation)
        self.assertEqual(expr.right.operator, "*")


class TestTrionInterpreter(unittest.TestCase):
    """Test the Trion interpreter."""
    
    def test_basic_execution(self):
        """Test basic code execution."""
        result = trion.run_trion("42")
        self.assertEqual(result, 42)
    
    def test_arithmetic(self):
        """Test arithmetic operations."""
        self.assertEqual(trion.run_trion("1 + 2"), 3)
        self.assertEqual(trion.run_trion("10 - 3"), 7)
        self.assertEqual(trion.run_trion("4 * 5"), 20)
        self.assertEqual(trion.run_trion("15 / 3"), 5.0)
        self.assertEqual(trion.run_trion("17 % 5"), 2)
        self.assertEqual(trion.run_trion("2 ** 3"), 8)
    
    def test_variables(self):
        """Test variable declaration and assignment."""
        code = """
        let x = 10
        x
        """
        self.assertEqual(trion.run_trion(code), 10)
    
    def test_functions(self):
        """Test function definition and calling."""
        code = """
        function add(a, b) {
            return a + b
        }
        add(3, 4)
        """
        self.assertEqual(trion.run_trion(code), 7)
    
    def test_control_flow(self):
        """Test if statements."""
        code = """
        let x = 5
        if x > 3 {
            42
        } else {
            0
        }
        """
        self.assertEqual(trion.run_trion(code), 42)
    
    def test_builtin_functions(self):
        """Test built-in functions."""
        # Test print function exists (doesn't return value)
        result = trion.run_trion('print("Hello")')
        self.assertIsNone(result)
        
        # Test type function
        self.assertEqual(trion.run_trion('type(42)'), 'int')
        self.assertEqual(trion.run_trion('type("hello")'), 'str')


class TestTrionLanguageFeatures(unittest.TestCase):
    """Test advanced language features."""
    
    def test_error_handling(self):
        """Test error handling with try-catch."""
        code = """
        try {
            let x = 1 / 0
        } catch {
            42
        }
        """
        # This should handle the division by zero gracefully
        result = trion.run_trion(code)
        self.assertEqual(result, 42)
    
    def test_loops(self):
        """Test while loops."""
        code = """
        let i = 0
        let sum = 0
        while i < 5 {
            sum = sum + i
            i = i + 1
        }
        sum
        """
        self.assertEqual(trion.run_trion(code), 10)  # 0+1+2+3+4 = 10
    
    def test_string_operations(self):
        """Test string operations."""
        self.assertEqual(trion.run_trion('"Hello" + " World"'), "Hello World")


if __name__ == '__main__':
    # Run all tests
    unittest.main(verbosity=2)