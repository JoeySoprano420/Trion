# Contributing to Trion

Thank you for your interest in contributing to the Trion programming language! This document provides guidelines for contributing to the project.

## Development Setup

### Prerequisites

- Python 3.8 or higher
- Git

### Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/your-username/Trion.git
   cd Trion
   ```

3. Install development dependencies:
   ```bash
   python build.py install-deps
   ```

4. Run the test suite to ensure everything is working:
   ```bash
   python build.py test
   ```

## Development Workflow

### Running Tests

```bash
# Run all tests
python build.py test

# Run specific test file
python tests/test_trion.py
```

### Code Formatting

```bash
# Format all code
python build.py format

# Check formatting/linting
python build.py lint
```

### Running Trion Programs

```bash
# Run a Trion program
python trion.py run examples/hello_world.tri

# Start interactive REPL
python trion.py repl

# Check syntax only
python trion.py check examples/fibonacci.tri
```

### Continuous Integration

```bash
# Run full CI pipeline (clean, lint, test, benchmark)
python build.py ci
```

## Project Structure

```
Trion/
├── src/                    # Source code
│   ├── lexer/             # Lexical analyzer
│   ├── parser/            # Parser (syntax analyzer)
│   ├── syntax_tree/       # Abstract Syntax Tree definitions
│   └── interpreter/       # Tree-walking interpreter
├── examples/              # Example Trion programs
├── tests/                 # Test suite
├── docs/                  # Documentation
├── trion.py              # Main CLI entry point
└── build.py              # Build system
```

## Language Development

### Adding Language Features

When adding new language features, follow these steps:

1. **Lexer**: Add new tokens to `TokenType` enum in `src/lexer/lexer.py`
2. **AST**: Add new AST node types in `src/syntax_tree/syntax_tree.py`
3. **Parser**: Add parsing logic in `src/parser/parser.py`
4. **Interpreter**: Add execution logic in `src/interpreter/interpreter.py`
5. **Tests**: Add comprehensive tests in `tests/test_trion.py`
6. **Documentation**: Update language specification in `docs/spec.md`

### Example: Adding a New Operator

To add a new operator (e.g., power operator `**`):

1. Add `POWER` to `TokenType` enum
2. Add `POWER` to `BinaryOperator` enum  
3. Update lexer to recognize `**` token
4. Update parser precedence and parsing logic
5. Add evaluation logic in interpreter
6. Add tests for the new operator

## Code Style Guidelines

### Python Code

- Follow PEP 8 style guidelines
- Use meaningful variable and function names
- Add docstrings to all public functions and classes
- Keep functions focused and under 50 lines when possible
- Use type hints where applicable

### Trion Code

- Use 4-space indentation
- Place opening braces on same line as declaration
- Use descriptive variable names
- Add comments for complex logic

### Commit Guidelines

- Use clear, descriptive commit messages
- Prefix commits with component: `lexer:`, `parser:`, `docs:`, etc.
- Keep commits focused on single changes
- Include tests with feature additions

Example commit messages:
```
lexer: Add support for hexadecimal integer literals
parser: Fix precedence issue with assignment operators  
interpreter: Implement break and continue statements
docs: Update getting started guide
tests: Add comprehensive error handling tests
```

## Testing Guidelines

### Unit Tests

- Write tests for all new features
- Test both success and error cases
- Use descriptive test names
- Keep tests focused and independent

### Integration Tests

- Test complete language features end-to-end
- Include example programs that demonstrate features
- Test error recovery and reporting

### Performance Tests

- Add benchmarks for performance-critical features
- Monitor performance regressions
- Document performance characteristics

## Documentation

### Language Specification

Keep `docs/spec.md` updated with:
- New language features
- Syntax examples
- Semantic behavior
- Type system rules

### API Documentation

- Document all public APIs
- Include usage examples
- Explain complex algorithms
- Keep documentation in sync with code

## Issue Reporting

When reporting issues:
- Use the issue templates
- Provide minimal reproduction cases
- Include system information
- Search for existing issues first

## Feature Requests

For new language features:
- Open an issue for discussion first
- Consider backward compatibility
- Provide motivation and use cases
- Consider implementation complexity

## Review Process

### Pull Request Guidelines

- Fork the repository and create a feature branch
- Make focused changes with clear commit history
- Add tests for new functionality
- Update documentation as needed
- Run full CI pipeline before submitting

### Review Criteria

- Code correctness and completeness
- Test coverage and quality
- Documentation updates
- Performance impact
- Backward compatibility
- Code style and clarity

## Release Process

### Versioning

Trion follows semantic versioning (SemVer):
- MAJOR: Incompatible API changes
- MINOR: Backward-compatible functionality additions
- PATCH: Backward-compatible bug fixes

### Release Checklist

- [ ] All tests pass
- [ ] Documentation is updated
- [ ] Changelog is updated
- [ ] Performance benchmarks are acceptable
- [ ] Examples work correctly
- [ ] Version numbers are updated

## Community Guidelines

### Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help newcomers learn and contribute
- Maintain professional communication

### Getting Help

- Check the documentation first
- Search existing issues and discussions
- Ask questions in GitHub discussions
- Join community chat channels

## Recognition

Contributors are recognized in:
- CONTRIBUTORS.md file
- Release notes
- Project documentation

## Long-term Vision

Trion aims to become a production-ready systems programming language with:
- Memory safety without garbage collection
- Zero-cost abstractions
- Excellent developer experience
- Strong ecosystem and tooling
- Active, welcoming community

Your contributions help make this vision a reality!

## Questions?

If you have questions about contributing, please:
- Open a discussion on GitHub
- Review existing documentation
- Reach out to maintainers

Thank you for contributing to Trion! 🚀