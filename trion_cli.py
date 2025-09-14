#!/usr/bin/env python3
"""
Trion Programming Language Command Line Interface
Provides REPL and file execution capabilities.
"""

import sys
import argparse
from typing import Optional
import trion


def repl():
    """Run the Trion REPL (Read-Eval-Print Loop)."""
    print("Trion Programming Language REPL")
    print(f"Version {trion.__version__}")
    print("Type 'exit' or 'quit' to leave, 'help' for help.\n")
    
    while True:
        try:
            line = input("trion> ")
            
            if line.strip().lower() in ['exit', 'quit']:
                print("Goodbye!")
                break
            
            if line.strip().lower() == 'help':
                print_help()
                continue
            
            if line.strip() == '':
                continue
            
            result = trion.run_trion(line, "<repl>")
            if result is not None:
                print(result)
                
        except KeyboardInterrupt:
            print("\nKeyboardInterrupt")
            break
        except EOFError:
            print("\nGoodbye!")
            break


def print_help():
    """Print REPL help."""
    print("""
Trion REPL Help:
- Type any Trion expression or statement to evaluate it
- Use 'exit' or 'quit' to leave the REPL
- Press Ctrl+C or Ctrl+D to exit
- Variables and functions persist across lines

Example usage:
  trion> let x = 5
  trion> let y = 10  
  trion> print(x + y)
  15
  
  trion> function greet(name) {
    print("Hello, " + name + "!")
  }
  trion> greet("World")
  Hello, World!
""")


def run_file(filename: str) -> int:
    """Run a Trion source file."""
    try:
        trion.run_file(filename)
        return 0  # Success if no exceptions
    except SystemExit as e:
        return e.code if e.code else 1
    except Exception:
        return 1


def main():
    """Main entry point for the Trion CLI."""
    parser = argparse.ArgumentParser(
        description="Trion Programming Language",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # Start REPL
  %(prog)s script.trion       # Run a Trion file
  %(prog)s -c "print('Hi')"   # Execute code directly
        """
    )
    
    parser.add_argument(
        'file',
        nargs='?',
        help='Trion source file to execute'
    )
    
    parser.add_argument(
        '-c', '--command',
        help='Execute a single command'
    )
    
    parser.add_argument(
        '-v', '--version',
        action='version',
        version=f'Trion {trion.__version__}'
    )
    
    args = parser.parse_args()
    
    try:
        if args.command:
            # Execute command directly
            try:
                trion.run_trion(args.command, "<command>")
                return 0  # Success if no exceptions
            except SystemExit as e:
                return e.code if e.code else 1
            except Exception:
                return 1
        
        elif args.file:
            # Run file
            return run_file(args.file)
        
        else:
            # Start REPL
            repl()
            return 0
            
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())