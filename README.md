# Trion Programming Language

**A powerful, error-free, adaptable, and resilient programming language**

Trion is a modern programming language designed with four core principles:
- **Powerful**: Rich feature set with expressive syntax
- **Error-free**: Comprehensive error handling and recovery mechanisms
- **Adaptable**: Flexible design supporting various programming paradigms
- **Resilient**: Robust architecture that gracefully handles edge cases

## Features

### Core Language Features
- **Dynamic typing** with optional type checking
- **First-class functions** with closures
- **Exception handling** with try-catch-finally blocks
- **Object-oriented programming** with classes and inheritance
- **Memory safe** with automatic memory management
- **Built-in data structures** (strings, numbers, arrays)

### Robust Error Handling
- Comprehensive lexical, syntax, and runtime error reporting
- Error recovery mechanisms in parser
- Detailed error messages with line and column information
- Graceful degradation on errors

### Developer Experience
- **REPL** for interactive development
- **Command-line interface** for script execution
- **Clear error messages** with context
- **Built-in functions** for common operations

## Installation

### Requirements
- Python 3.7 or higher

### Setup
```bash
# Clone the repository
git clone https://github.com/JoeySoprano420/Trion.git
cd Trion

# Make CLI executable (optional)
chmod +x trion_cli.py
```

## Usage

### Interactive REPL
```bash
python trion_cli.py
```

### Run a Trion file
```bash
python trion_cli.py examples/hello.trion
```

### Execute code directly
```bash
python trion_cli.py -c 'print("Hello from Trion!")'
```

## Language Syntax

### Variables
```trion
let x = 42
const PI = 3.14159
let name = "Trion"
```

### Functions
```trion
function greet(name) {
    return "Hello, " + name + "!"
}

let message = greet("World")
print(message)
```

### Control Flow
```trion
// If-else statements
if x > 0 {
    print("Positive")
} elif x < 0 {
    print("Negative")
} else {
    print("Zero")
}

// While loops
let i = 0
while i < 5 {
    print(i)
    i = i + 1
}
```

### Error Handling
```trion
try {
    let result = risky_operation()
} catch (error) {
    print("Error: " + str(error))
} finally {
    print("Cleanup completed")
}
```

### Classes (Basic Support)
```trion
class Calculator {
    function add(a, b) {
        return a + b
    }
    
    function multiply(a, b) {
        return a * b
    }
}
```

## Built-in Functions

- `print(...)` - Print values to stdout
- `type(obj)` - Get the type of an object
- `str(obj)` - Convert object to string
- `int(obj)` - Convert object to integer
- `float(obj)` - Convert object to float
- `len(obj)` - Get length of collection

## Examples

See the `examples/` directory for sample programs:
- `hello.trion` - Basic hello world
- `calculator.trion` - Functions and control flow
- `error_handling.trion` - Exception handling examples

## Architecture

Trion follows a traditional interpreter architecture:

1. **Lexer** (`trion/lexer.py`) - Tokenizes source code
2. **Parser** (`trion/parser.py`) - Builds Abstract Syntax Tree (AST)
3. **Interpreter** (`trion/interpreter.py`) - Executes the AST

### Error Recovery
- The lexer continues on invalid characters, marking them as INVALID tokens
- The parser uses panic mode recovery to resynchronize after errors
- The interpreter provides detailed runtime error information

### Type System
- Dynamic typing with runtime type checking
- Type conversion functions for explicit casting
- Type information available through built-in functions

## Testing

Run the test suite:
```bash
python -m pytest tests/test_trion.py -v
```

Or using unittest:
```bash
python tests/test_trion.py
```

## Development

### Project Structure
```
Trion/
├── trion/                 # Core language implementation
│   ├── __init__.py       # Package initialization and main API
│   ├── lexer.py          # Lexical analyzer
│   ├── parser.py         # Recursive descent parser
│   ├── interpreter.py    # AST interpreter
│   ├── ast_nodes.py      # AST node definitions
│   ├── token.py          # Token class
│   ├── token_types.py    # Token type definitions
│   └── errors.py         # Error handling system
├── tests/                # Test suite
├── examples/             # Example programs
├── trion_cli.py          # Command-line interface
└── README.md            # This file
```

### Design Principles

1. **Resilience**: The language gracefully handles errors and edge cases
2. **Adaptability**: Modular design allows easy extension and modification  
3. **Power**: Rich feature set supports complex programming tasks
4. **Error-free**: Comprehensive error checking and reporting at all levels

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## License

This project is open source and available under the MIT License.

## Version History

- **v0.1.0** - Initial release with core language features
  - Lexical analysis with error recovery
  - Recursive descent parser with error handling
  - Tree-walking interpreter
  - Basic type system and built-in functions
  - Exception handling (try-catch-finally)
  - Interactive REPL and CLI
  - Comprehensive test suite