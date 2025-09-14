# Trion Language Specification v0.1.0

## Overview

Trion is a statically-typed, compiled programming language designed for system programming, application development, and performance-critical software.

## Design Principles

1. **Safety First**: Memory safety without garbage collection overhead
2. **Zero-Cost Abstractions**: High-level features with no runtime cost
3. **Explicit Control**: Developers have control over performance-critical aspects
4. **Ergonomic**: Pleasant developer experience with clear, readable syntax
5. **Interoperable**: Easy integration with C/C++ and other languages

## Syntax Overview

### Basic Types

```trion
// Integer types
let x: i32 = 42;        // 32-bit signed integer
let y: u64 = 1000;      // 64-bit unsigned integer
let z: isize = -1;      // pointer-sized signed integer

// Floating point
let pi: f64 = 3.14159;  // 64-bit float
let e: f32 = 2.718f;    // 32-bit float

// Boolean and character
let flag: bool = true;
let ch: char = 'A';

// Strings
let name: str = "Trion";        // String slice (borrowed)
let owned: String = "Hello";    // Owned string
```

### Variables and Mutability

```trion
let x = 10;           // Immutable by default
let mut y = 20;       // Explicitly mutable
y = 30;               // OK - y is mutable
// x = 15;            // Error - x is immutable
```

### Functions

```trion
// Basic function
fn add(a: i32, b: i32) -> i32 {
    return a + b;
}

// Function with type inference
fn multiply(a: i32, b: i32) -> i32 {
    a * b  // Implicit return
}

// Generic function
fn max<T: Ord>(a: T, b: T) -> T {
    if a > b { a } else { b }
}
```

### Control Flow

```trion
// If expressions
let result = if condition {
    value1
} else {
    value2
};

// Pattern matching
match value {
    1 => println("One"),
    2 | 3 => println("Two or Three"),
    x if x > 10 => println("Greater than 10: {}", x),
    _ => println("Something else"),
}

// Loops
for i in 0..10 {
    println("i = {}", i);
}

while condition {
    // loop body
}

loop {
    // infinite loop
    if exit_condition {
        break;
    }
}
```

### Structs and Enums

```trion
// Struct definition
struct Point {
    x: f64,
    y: f64,
}

impl Point {
    fn new(x: f64, y: f64) -> Point {
        Point { x, y }
    }
    
    fn distance(&self, other: &Point) -> f64 {
        ((self.x - other.x).pow(2) + (self.y - other.y).pow(2)).sqrt()
    }
}

// Enum definition
enum Result<T, E> {
    Ok(T),
    Err(E),
}
```

### Memory Management

Trion uses a ownership system similar to Rust but with some ergonomic improvements:

```trion
// Ownership transfer
let s1 = String::new("Hello");
let s2 = s1;  // s1 is no longer valid

// Borrowing
fn print_string(s: &str) {
    println("{}", s);
}

let text = String::new("World");
print_string(&text);  // Borrow text
println("{}", text);   // text still valid
```

### Modules and Imports

```trion
// Define a module
mod math {
    pub fn add(a: i32, b: i32) -> i32 {
        a + b
    }
    
    fn private_function() {
        // Only accessible within this module
    }
}

// Use items from modules
use math::add;
use std::collections::HashMap;

// External crate
extern crate regex;
use regex::Regex;
```

### Error Handling

```trion
// Result type for error handling
fn divide(a: f64, b: f64) -> Result<f64, &'static str> {
    if b == 0.0 {
        Err("Division by zero")
    } else {
        Ok(a / b)
    }
}

// Using ? operator for early return
fn process_data() -> Result<String, Error> {
    let data = read_file("input.txt")?;
    let processed = transform_data(data)?;
    Ok(processed)
}
```

### Concurrency

```trion
// Threads
spawn(|| {
    println("Running in thread");
});

// Channels for communication
let (tx, rx) = channel();
spawn(move || {
    tx.send("Hello from thread");
});

let msg = rx.recv();
println("Received: {}", msg);

// Async/await
async fn fetch_data() -> Result<String, Error> {
    let response = http_get("https://api.example.com/data").await?;
    Ok(response.text())
}
```

## Standard Library

The Trion standard library provides:

- Core data types and operations
- Collections (Vec, HashMap, HashSet, etc.)
- I/O operations
- Networking support
- Concurrency primitives
- Regular expressions
- JSON/serialization support
- File system operations

## Compilation Model

Trion compiles to native machine code through LLVM backend:

1. **Lexical Analysis**: Source code → Tokens
2. **Parsing**: Tokens → Abstract Syntax Tree (AST)
3. **Semantic Analysis**: Type checking, borrow checking
4. **Optimization**: Various optimization passes
5. **Code Generation**: LLVM IR → Native code

## Future Features

- Compile-time evaluation
- Procedural macros
- Foreign function interface (FFI)
- Package management
- Cross-compilation support
- WebAssembly target