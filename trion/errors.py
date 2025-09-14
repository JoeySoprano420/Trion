"""
Error handling system for Trion programming language.
Provides comprehensive error reporting for resilient error management.
"""

class TrionError(Exception):
    """Base class for all Trion language errors."""
    
    def __init__(self, message, line=None, column=None, filename=None):
        super().__init__(message)
        self.message = message
        self.line = line
        self.column = column
        self.filename = filename
    
    def __str__(self):
        location = ""
        if self.filename:
            location += f"File \"{self.filename}\""
        if self.line is not None:
            location += f", line {self.line}"
        if self.column is not None:
            location += f", column {self.column}"
        
        if location:
            return f"{self.__class__.__name__}: {location}\n  {self.message}"
        return f"{self.__class__.__name__}: {self.message}"


class LexerError(TrionError):
    """Error during lexical analysis."""
    pass


class SyntaxError(TrionError):
    """Error during parsing."""
    pass


class TypeError(TrionError):
    """Type-related error."""
    pass


class RuntimeError(TrionError):
    """Runtime execution error."""
    pass


class NameError(TrionError):
    """Name resolution error."""
    pass


class ValueError(TrionError):
    """Value-related error."""
    pass


class ImportError(TrionError):
    """Module import error."""
    pass


class ErrorReporter:
    """Centralized error reporting system for better error handling."""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
    
    def error(self, message, line=None, column=None, filename=None):
        """Report an error."""
        error = TrionError(message, line, column, filename)
        self.errors.append(error)
        return error
    
    def syntax_error(self, message, line=None, column=None, filename=None):
        """Report a syntax error."""
        error = SyntaxError(message, line, column, filename)
        self.errors.append(error)
        return error
    
    def type_error(self, message, line=None, column=None, filename=None):
        """Report a type error."""
        error = TypeError(message, line, column, filename)
        self.errors.append(error)
        return error
    
    def runtime_error(self, message, line=None, column=None, filename=None):
        """Report a runtime error."""
        error = RuntimeError(message, line, column, filename)
        self.errors.append(error)
        return error
    
    def warning(self, message, line=None, column=None, filename=None):
        """Report a warning."""
        warning = TrionError(message, line, column, filename)
        self.warnings.append(warning)
        return warning
    
    def has_errors(self):
        """Check if there are any errors."""
        return len(self.errors) > 0
    
    def has_warnings(self):
        """Check if there are any warnings."""
        return len(self.warnings) > 0
    
    def clear(self):
        """Clear all errors and warnings."""
        self.errors.clear()
        self.warnings.clear()
    
    def print_errors(self):
        """Print all errors to stderr."""
        for error in self.errors:
            print(str(error), file=sys.stderr)
    
    def print_warnings(self):
        """Print all warnings to stderr."""
        for warning in self.warnings:
            print(f"Warning: {warning}", file=sys.stderr)


import sys