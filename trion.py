#!/usr/bin/env python3
"""
Trion Language Command Line Interface

This is the main entry point for the Trion programming language.
It provides commands for running, testing, and managing Trion code.
"""

import sys
import os
import argparse
from pathlib import Path

# Add the src directory to path so we can import our modules
current_dir = Path(__file__).parent
src_dir = current_dir / "src"
sys.path.insert(0, str(src_dir))

from lexer.lexer import Lexer, LexerError
from parser.parser import Parser, ParseError
from interpreter.interpreter import Interpreter
from syntax_tree.syntax_tree import ASTPrinter

def run_file(file_path: str, debug: bool = False):
    """Run a Trion source file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source_code = f.read()
        
        if debug:
            print(f"Running {file_path}...")
        
        # Tokenize
        lexer = Lexer(source_code)
        tokens = lexer.tokenize()
        
        if debug:
            print("Tokens:")
            for token in tokens:
                if token.type.name != 'EOF':
                    print(f"  {token}")
            print()
        
        # Parse
        parser = Parser(tokens)
        program = parser.parse()
        
        if debug:
            printer = ASTPrinter()
            print("AST:")
            print(printer.visit_program(program))
            print()
        
        # Interpret
        interpreter = Interpreter()
        success = interpreter.interpret(program)
        
        return success
        
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        return False
    except LexerError as e:
        print(f"Lexer Error: {e}")
        return False
    except ParseError as e:
        print(f"Parse Error: {e}")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False

def run_interactive():
    """Run Trion in interactive REPL mode."""
    print("Trion REPL v0.1.0")
    print("Type 'exit' to quit, 'help' for help")
    print()
    
    interpreter = Interpreter()
    
    while True:
        try:
            source = input("trion> ")
            
            if source.strip() == "exit":
                break
            elif source.strip() == "help":
                print("Commands:")
                print("  exit - Exit the REPL")
                print("  help - Show this help message")
                print("  Any valid Trion expression or statement")
                continue
            elif source.strip() == "":
                continue
            
            # For REPL, we need to handle single expressions
            if not source.strip().endswith(';'):
                source = source.strip() + ';'
            
            # Tokenize
            lexer = Lexer(source)
            tokens = lexer.tokenize()
            
            # Parse
            parser = Parser(tokens)
            program = parser.parse()
            
            # Interpret
            interpreter.interpret(program)
            
        except KeyboardInterrupt:
            print("\nUse 'exit' to quit.")
        except EOFError:
            break
        except Exception as e:
            print(f"Error: {e}")
    
    print("Goodbye!")

def check_syntax(file_path: str):
    """Check syntax of a Trion file without executing it."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source_code = f.read()
        
        # Tokenize
        lexer = Lexer(source_code)
        tokens = lexer.tokenize()
        
        # Parse
        parser = Parser(tokens)
        program = parser.parse()
        
        print(f"Syntax OK: {file_path}")
        return True
        
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        return False
    except (LexerError, ParseError) as e:
        print(f"Syntax Error in {file_path}: {e}")
        return False
    except Exception as e:
        print(f"Error checking {file_path}: {e}")
        return False

def format_file(file_path: str, dry_run: bool = False):
    """Format a Trion source file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source_code = f.read()
        
        # Tokenize and parse
        lexer = Lexer(source_code)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        program = parser.parse()
        
        # Pretty print
        printer = ASTPrinter()
        formatted_code = printer.visit_program(program)
        
        if dry_run:
            print(f"Formatted {file_path}:")
            print(formatted_code)
        else:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(formatted_code)
            print(f"Formatted: {file_path}")
        
        return True
        
    except Exception as e:
        print(f"Error formatting {file_path}: {e}")
        return False

def main():
    """Main entry point for Trion CLI."""
    parser = argparse.ArgumentParser(
        description="Trion Programming Language",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  trion                    # Start interactive REPL
  trion run script.tri     # Run a Trion script
  trion check script.tri   # Check syntax
  trion format script.tri  # Format code
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Run command
    run_parser = subparsers.add_parser('run', help='Run a Trion script')
    run_parser.add_argument('file', help='Trion source file to run')
    run_parser.add_argument('--debug', action='store_true', help='Enable debug output')
    
    # Check command
    check_parser = subparsers.add_parser('check', help='Check syntax of a Trion file')
    check_parser.add_argument('file', help='Trion source file to check')
    
    # Format command
    format_parser = subparsers.add_parser('format', help='Format a Trion source file')
    format_parser.add_argument('file', help='Trion source file to format')
    format_parser.add_argument('--dry-run', action='store_true', 
                              help='Show formatted output without modifying file')
    
    # REPL command (default)
    repl_parser = subparsers.add_parser('repl', help='Start interactive REPL')
    
    args = parser.parse_args()
    
    # If no command specified, start REPL
    if not args.command:
        run_interactive()
        return
    
    # Handle commands
    if args.command == 'run':
        success = run_file(args.file, args.debug)
        sys.exit(0 if success else 1)
    elif args.command == 'check':
        success = check_syntax(args.file)
        sys.exit(0 if success else 1)
    elif args.command == 'format':
        success = format_file(args.file, args.dry_run)
        sys.exit(0 if success else 1)
    elif args.command == 'repl':
        run_interactive()
    else:
        parser.print_help()

if __name__ == '__main__':
    main()