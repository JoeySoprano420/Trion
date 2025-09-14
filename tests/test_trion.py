#!/usr/bin/env python3
"""
Trion Language Test Suite

Comprehensive testing framework for the Trion programming language.
"""

import sys
import os
import unittest
import tempfile
from pathlib import Path

# Add the src directory to path
current_dir = Path(__file__).parent.parent  # Go up from tests/ to project root
src_dir = current_dir / "src"
sys.path.insert(0, str(src_dir))

from lexer.lexer import Lexer, TokenType, LexerError
from parser.parser import Parser, ParseError
from interpreter.interpreter import Interpreter
from syntax_tree.syntax_tree import *

class TestLexer(unittest.TestCase):
    """Test cases for the lexer."""
    
    def test_basic_tokens(self):
        """Test basic token recognition."""
        source = "let x = 42;"
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        
        expected_types = [TokenType.LET, TokenType.IDENTIFIER, TokenType.ASSIGN, 
                         TokenType.INTEGER, TokenType.SEMICOLON, TokenType.EOF]
        
        actual_types = [token.type for token in tokens]
        self.assertEqual(actual_types, expected_types)
    
    def test_string_literals(self):
        """Test string literal tokenization."""
        source = '"Hello, World!"'
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        
        self.assertEqual(tokens[0].type, TokenType.STRING)
        self.assertEqual(tokens[0].value, "Hello, World!")
    
    def test_numbers(self):
        """Test number tokenization."""
        source = "42 3.14 2.5e-3"
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        
        self.assertEqual(tokens[0].type, TokenType.INTEGER)
        self.assertEqual(tokens[0].value, "42")
        
        self.assertEqual(tokens[1].type, TokenType.FLOAT)
        self.assertEqual(tokens[1].value, "3.14")
        
        self.assertEqual(tokens[2].type, TokenType.FLOAT)
        self.assertEqual(tokens[2].value, "2.5e-3")
    
    def test_keywords(self):
        """Test keyword recognition."""
        source = "fn let if else while for return"
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        
        expected_types = [TokenType.FN, TokenType.LET, TokenType.IF, TokenType.ELSE, 
                         TokenType.WHILE, TokenType.FOR, TokenType.RETURN, TokenType.EOF]
        
        actual_types = [token.type for token in tokens]
        self.assertEqual(actual_types, expected_types)
    
    def test_operators(self):
        """Test operator tokenization."""
        source = "+ - * / % == != < > <= >= && ||"
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        
        expected_types = [
            TokenType.PLUS, TokenType.MINUS, TokenType.MULTIPLY, TokenType.DIVIDE,
            TokenType.MODULO, TokenType.EQUAL, TokenType.NOT_EQUAL, TokenType.LESS,
            TokenType.GREATER, TokenType.LESS_EQUAL, TokenType.GREATER_EQUAL,
            TokenType.AND, TokenType.OR, TokenType.EOF
        ]
        
        actual_types = [token.type for token in tokens]
        self.assertEqual(actual_types, expected_types)

class TestParser(unittest.TestCase):
    """Test cases for the parser."""
    
    def parse_source(self, source: str) -> Program:
        """Helper to parse source code."""
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        return parser.parse()
    
    def test_variable_declaration(self):
        """Test variable declaration parsing."""
        source = "let x: i32 = 42;"
        program = self.parse_source(source)
        
        self.assertEqual(len(program.statements), 1)
        stmt = program.statements[0]
        self.assertIsInstance(stmt, VariableDeclaration)
        self.assertEqual(stmt.name, "x")
        self.assertIsNotNone(stmt.type_annotation)
        self.assertIsInstance(stmt.initializer, IntegerLiteral)
    
    def test_function_declaration(self):
        """Test function declaration parsing."""
        source = """
        fn add(a: i32, b: i32) -> i32 {
            return a + b;
        }
        """
        program = self.parse_source(source)
        
        self.assertEqual(len(program.statements), 1)
        func = program.statements[0]
        self.assertIsInstance(func, FunctionDeclaration)
        self.assertEqual(func.name, "add")
        self.assertEqual(len(func.parameters), 2)
        self.assertIsNotNone(func.return_type)
        self.assertIsInstance(func.body, BlockStatement)
    
    def test_binary_expressions(self):
        """Test binary expression parsing."""
        source = "let x = 1 + 2 * 3;"
        program = self.parse_source(source)
        
        stmt = program.statements[0]
        self.assertIsInstance(stmt, VariableDeclaration)
        
        expr = stmt.initializer
        self.assertIsInstance(expr, BinaryExpression)
        self.assertEqual(expr.operator, BinaryOperator.ADD)
        
        # Should be: 1 + (2 * 3) due to precedence
        right_expr = expr.right
        self.assertIsInstance(right_expr, BinaryExpression)
        self.assertEqual(right_expr.operator, BinaryOperator.MULTIPLY)
    
    def test_if_statement(self):
        """Test if statement parsing."""
        source = """
        if x > 0 {
            println("positive");
        } else {
            println("non-positive");
        }
        """
        program = self.parse_source(source)
        
        stmt = program.statements[0]
        self.assertIsInstance(stmt, IfStatement)
        self.assertIsNotNone(stmt.condition)
        self.assertIsNotNone(stmt.then_branch)
        self.assertIsNotNone(stmt.else_branch)

class TestInterpreter(unittest.TestCase):
    """Test cases for the interpreter."""
    
    def run_source(self, source: str) -> bool:
        """Helper to run source code."""
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        program = parser.parse()
        interpreter = Interpreter()
        return interpreter.interpret(program)
    
    def test_arithmetic(self):
        """Test arithmetic operations."""
        # Capture output for testing
        import io
        from contextlib import redirect_stdout
        
        source = """
        let x = 2 + 3 * 4;
        println(x);
        """
        
        f = io.StringIO()
        with redirect_stdout(f):
            success = self.run_source(source)
        
        self.assertTrue(success)
        output = f.getvalue().strip()
        self.assertEqual(output, "14")  # Should be 2 + (3 * 4) = 14
    
    def test_function_call(self):
        """Test function calls."""
        import io
        from contextlib import redirect_stdout
        
        source = """
        fn double(x: i32) -> i32 {
            return x * 2;
        }
        
        println(double(21));
        """
        
        f = io.StringIO()
        with redirect_stdout(f):
            success = self.run_source(source)
        
        self.assertTrue(success)
        output = f.getvalue().strip()
        self.assertEqual(output, "42")
    
    def test_recursive_function(self):
        """Test recursive function calls."""
        import io
        from contextlib import redirect_stdout
        
        source = """
        fn factorial(n: i32) -> i32 {
            if n <= 1 {
                return 1;
            }
            return n * factorial(n - 1);
        }
        
        println(factorial(5));
        """
        
        f = io.StringIO()
        with redirect_stdout(f):
            success = self.run_source(source)
        
        self.assertTrue(success)
        output = f.getvalue().strip()
        self.assertEqual(output, "120")  # 5! = 120
    
    def test_while_loop(self):
        """Test while loop execution."""
        import io
        from contextlib import redirect_stdout
        
        source = """
        let mut i = 0;
        let mut sum = 0;
        while i < 5 {
            sum = sum + i;
            i = i + 1;
        }
        println(sum);
        """
        
        f = io.StringIO()
        with redirect_stdout(f):
            success = self.run_source(source)
        
        self.assertTrue(success)
        output = f.getvalue().strip()
        self.assertEqual(output, "10")  # 0 + 1 + 2 + 3 + 4 = 10
    
    def test_variable_scoping(self):
        """Test variable scoping in blocks."""
        import io
        from contextlib import redirect_stdout
        
        source = """
        let x = 10;
        {
            let x = 20;
            println(x);
        }
        println(x);
        """
        
        f = io.StringIO()
        with redirect_stdout(f):
            success = self.run_source(source)
        
        self.assertTrue(success)
        output = f.getvalue().strip().split('\n')
        self.assertEqual(output[0], "20")  # Inner scope
        self.assertEqual(output[1], "10")  # Outer scope

class TestExamples(unittest.TestCase):
    """Test cases for example programs."""
    
    def test_hello_world(self):
        """Test hello world example."""
        import io
        from contextlib import redirect_stdout
        
        with open('examples/hello_world.tri', 'r') as f:
            source = f.read()
        
        f = io.StringIO()
        with redirect_stdout(f):
            lexer = Lexer(source)
            tokens = lexer.tokenize()
            parser = Parser(tokens)
            program = parser.parse()
            interpreter = Interpreter()
            success = interpreter.interpret(program)
        
        self.assertTrue(success)
        output = f.getvalue().strip()
        self.assertEqual(output, "Hello, World!")
    
    def test_fibonacci(self):
        """Test fibonacci example."""
        import io
        from contextlib import redirect_stdout
        
        # Simplified fibonacci test
        source = """
        fn fibonacci(n: i32) -> i32 {
            if n <= 1 {
                return n;
            }
            return fibonacci(n - 1) + fibonacci(n - 2);
        }
        
        println(fibonacci(7));
        """
        
        f = io.StringIO()
        with redirect_stdout(f):
            lexer = Lexer(source)
            tokens = lexer.tokenize()
            parser = Parser(tokens)
            program = parser.parse()
            interpreter = Interpreter()
            success = interpreter.interpret(program)
        
        self.assertTrue(success)
        output = f.getvalue().strip()
        self.assertEqual(output, "13")  # fibonacci(7) = 13

class TestErrorHandling(unittest.TestCase):
    """Test error handling and edge cases."""
    
    def test_lexer_error(self):
        """Test lexer error handling."""
        source = '"unterminated string'
        
        with self.assertRaises(LexerError):
            lexer = Lexer(source)
            tokens = lexer.tokenize()
    
    def test_parser_error(self):
        """Test parser error handling."""
        source = "let = 42;"  # Missing variable name
        
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        
        # Parser should handle errors gracefully
        program = parser.parse()
        # The program should have recovered or have no statements due to error
        self.assertIsInstance(program, Program)
    
    def test_runtime_error(self):
        """Test runtime error handling."""
        source = """
        let x = 10 / 0;  // Division by zero
        """
        
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        program = parser.parse()
        interpreter = Interpreter()
        
        # Should handle runtime error gracefully
        success = interpreter.interpret(program)
        self.assertFalse(success)

def run_tests():
    """Run all tests."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestLexer))
    suite.addTests(loader.loadTestsFromTestCase(TestParser))
    suite.addTests(loader.loadTestsFromTestCase(TestInterpreter))
    suite.addTests(loader.loadTestsFromTestCase(TestExamples))
    suite.addTests(loader.loadTestsFromTestCase(TestErrorHandling))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()

if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)