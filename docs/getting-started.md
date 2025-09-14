# Getting Started with Trion

This guide will help you get up and running with the Trion programming language.

## Installation

Currently, Trion is run through Python. Future releases will include standalone binaries.

### Prerequisites

- Python 3.8 or higher
- Git (for cloning the repository)

### Download and Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/JoeySoprano420/Trion.git
   cd Trion
   ```

2. Verify installation:
   ```bash
   python trion.py --help
   ```

## Your First Trion Program

Create a file named `hello.tri`:

```trion
fn main() {
    println("Hello, Trion!");
}

main();
```

Run it:

```bash
python trion.py run hello.tri
```

You should see:
```
Hello, Trion!
```

## Basic Syntax

### Variables

```trion
// Immutable variables (default)
let x = 42;
let name = "Alice";

// Mutable variables
let mut count = 0;
count = count + 1;

// Type annotations
let age: i32 = 25;
let pi: f64 = 3.14159;
```

### Data Types

```trion
// Integers
let small: i32 = 100;
let big: i64 = 1000000;

// Floats
let precise: f64 = 3.14159265359;
let simple: f32 = 2.718f;

// Booleans
let yes: bool = true;
let no = false;

// Strings
let greeting = "Hello, World!";
let letter: char = 'A';
```

### Functions

```trion
// Simple function
fn greet(name: str) {
    println("Hello,", name);
}

// Function with return value
fn add(a: i32, b: i32) -> i32 {
    return a + b;
}

// Function with implicit return
fn multiply(x: i32, y: i32) -> i32 {
    x * y
}

// Using functions
greet("World");
let sum = add(5, 3);
let product = multiply(4, 7);
```

### Control Flow

#### If Statements

```trion
let x = 10;

if x > 0 {
    println("Positive");
} else if x < 0 {
    println("Negative");
} else {
    println("Zero");
}

// If as expression
let sign = if x > 0 {
    "positive"
} else {
    "negative or zero"
};
```

#### Loops

```trion
// While loop
let mut i = 0;
while i < 5 {
    println("Count:", i);
    i = i + 1;
}

// Infinite loop with break
let mut counter = 0;
loop {
    counter = counter + 1;
    if counter > 10 {
        break;
    }
    if counter % 2 == 0 {
        continue;
    }
    println("Odd:", counter);
}
```

## Examples

### Fibonacci Sequence

```trion
fn fibonacci(n: i32) -> i32 {
    if n <= 1 {
        return n;
    }
    return fibonacci(n - 1) + fibonacci(n - 2);
}

fn main() {
    let mut i = 0;
    while i <= 10 {
        println("fib(", i, ") =", fibonacci(i));
        i = i + 1;
    }
}

main();
```

### Prime Numbers

```trion
fn is_prime(n: i32) -> bool {
    if n <= 1 {
        return false;
    }
    if n <= 3 {
        return true;
    }
    if n % 2 == 0 {
        return false;
    }
    
    let mut i = 3;
    while i * i <= n {
        if n % i == 0 {
            return false;
        }
        i = i + 2;
    }
    return true;
}

fn main() {
    println("Primes up to 100:");
    let mut i = 2;
    while i <= 100 {
        if is_prime(i) {
            println(i);
        }
        i = i + 1;
    }
}

main();
```

### Calculator

```trion
fn add(a: i32, b: i32) -> i32 {
    return a + b;
}

fn subtract(a: i32, b: i32) -> i32 {
    return a - b;
}

fn multiply(a: i32, b: i32) -> i32 {
    return a * b;
}

fn divide(a: i32, b: i32) -> i32 {
    if b == 0 {
        println("Error: Division by zero");
        return 0;
    }
    return a / b;
}

fn main() {
    let x = 15;
    let y = 3;
    
    println(x, "+", y, "=", add(x, y));
    println(x, "-", y, "=", subtract(x, y));
    println(x, "*", y, "=", multiply(x, y));
    println(x, "/", y, "=", divide(x, y));
}

main();
```

## Interactive REPL

Trion includes an interactive Read-Eval-Print Loop (REPL) for experimenting:

```bash
python trion.py repl
```

Example REPL session:
```
Trion REPL v0.1.0
Type 'exit' to quit, 'help' for help

trion> let x = 42;
trion> println(x);
42
trion> let y = x * 2;
trion> println("Double x is", y);
Double x is 84
trion> exit
Goodbye!
```

## Development Tools

### Syntax Checking

Check if your Trion code has correct syntax:

```bash
python trion.py check my_program.tri
```

### Code Formatting

Format your Trion code:

```bash
python trion.py format my_program.tri
```

### Debug Mode

Run with debug information:

```bash
python trion.py run --debug my_program.tri
```

This shows:
- Tokenization output
- Abstract Syntax Tree
- Execution trace

## Tips and Best Practices

### Variable Naming

- Use descriptive names: `user_count` not `n`
- Use snake_case: `first_name` not `firstName`
- Constants in UPPER_CASE (when supported)

### Function Design

- Keep functions small and focused
- Use meaningful parameter names
- Include return type annotations
- One responsibility per function

### Code Organization

- Group related functions together
- Use consistent indentation (4 spaces)
- Add comments for complex logic
- Separate concerns into modules (when supported)

### Performance

- Prefer immutable variables when possible
- Avoid deep recursion for large inputs
- Use appropriate data types
- Profile performance-critical code

## Common Patterns

### Input Validation

```trion
fn safe_divide(a: i32, b: i32) -> i32 {
    if b == 0 {
        println("Error: Cannot divide by zero");
        return 0;
    }
    return a / b;
}
```

### Accumulator Pattern

```trion
fn sum_up_to(n: i32) -> i32 {
    let mut sum = 0;
    let mut i = 1;
    while i <= n {
        sum = sum + i;
        i = i + 1;
    }
    return sum;
}
```

### Counter Pattern

```trion
fn count_digits(mut n: i32) -> i32 {
    if n == 0 {
        return 1;
    }
    
    let mut count = 0;
    while n > 0 {
        n = n / 10;
        count = count + 1;
    }
    return count;
}
```

## Next Steps

1. **Explore Examples**: Check out the `examples/` directory for more programs
2. **Read the Specification**: See `docs/spec.md` for complete language details
3. **Join the Community**: Contribute to discussions and development
4. **Build Something**: Create your own Trion programs

## Getting Help

- Check this documentation
- Look at example programs
- Use the REPL to experiment
- Report issues on GitHub
- Join community discussions

Welcome to the Trion programming language! Happy coding! 🚀