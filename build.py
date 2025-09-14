#!/usr/bin/env python3
"""
Trion Language Build System

This script handles building, testing, and packaging the Trion language.
"""

import sys
import os
import subprocess
import argparse
from pathlib import Path

def run_command(cmd, description=""):
    """Run a command and return success status."""
    if description:
        print(f"Running: {description}")
    
    print(f"$ {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    
    if isinstance(cmd, str):
        result = subprocess.run(cmd, shell=True)
    else:
        result = subprocess.run(cmd)
    
    if result.returncode != 0:
        print(f"✗ Failed: {description or cmd}")
        return False
    else:
        print(f"✓ Success: {description or cmd}")
        return True

def test():
    """Run all tests."""
    print("=" * 50)
    print("Running Trion Test Suite")
    print("=" * 50)
    
    # Run unit tests
    success = run_command([sys.executable, "tests/test_trion.py"], 
                         "Unit tests")
    
    if success:
        print("\n" + "=" * 50)
        print("✓ All tests passed!")
        print("=" * 50)
    else:
        print("\n" + "=" * 50)
        print("✗ Some tests failed!")
        print("=" * 50)
    
    return success

def lint():
    """Run linting on the codebase."""
    print("=" * 50)
    print("Running Linting")
    print("=" * 50)
    
    # Check if flake8 is available
    try:
        subprocess.run(["flake8", "--version"], check=True, capture_output=True)
        has_flake8 = True
    except (subprocess.CalledProcessError, FileNotFoundError):
        has_flake8 = False
    
    if has_flake8:
        success = run_command(["flake8", "src/", "tests/", "trion.py"], 
                             "Python linting")
    else:
        print("flake8 not found, skipping Python linting")
        success = True
    
    # Check syntax of example files
    example_files = list(Path("examples").glob("*.tri"))
    for example in example_files:
        cmd_success = run_command([sys.executable, "trion.py", "check", str(example)],
                                 f"Syntax check: {example}")
        success = success and cmd_success
    
    if success:
        print("\n" + "=" * 50)
        print("✓ All linting passed!")
        print("=" * 50)
    else:
        print("\n" + "=" * 50)
        print("✗ Some linting issues found!")
        print("=" * 50)
    
    return success

def format_code():
    """Format Trion source files."""
    print("=" * 50)
    print("Formatting Trion Code")
    print("=" * 50)
    
    success = True
    
    # Format example files
    example_files = list(Path("examples").glob("*.tri"))
    for example in example_files:
        cmd_success = run_command([sys.executable, "trion.py", "format", str(example)],
                                 f"Format: {example}")
        success = success and cmd_success
    
    # Format Python code if black is available
    try:
        subprocess.run(["black", "--version"], check=True, capture_output=True)
        has_black = True
    except (subprocess.CalledProcessError, FileNotFoundError):
        has_black = False
    
    if has_black:
        cmd_success = run_command(["black", "src/", "tests/", "trion.py"], 
                                 "Python formatting")
        success = success and cmd_success
    else:
        print("black not found, skipping Python formatting")
    
    return success

def benchmark():
    """Run performance benchmarks."""
    print("=" * 50)
    print("Running Benchmarks")
    print("=" * 50)
    
    # Simple benchmark: time fibonacci calculation
    import time
    
    benchmark_code = """
    fn fibonacci(n: i32) -> i32 {
        if n <= 1 {
            return n;
        }
        return fibonacci(n - 1) + fibonacci(n - 2);
    }
    
    fibonacci(25);
    """
    
    # Write to temporary file
    with open("benchmark_temp.tri", "w") as f:
        f.write(benchmark_code)
    
    try:
        start_time = time.time()
        success = run_command([sys.executable, "trion.py", "run", "benchmark_temp.tri"],
                             "Fibonacci benchmark")
        end_time = time.time()
        
        if success:
            elapsed = end_time - start_time
            print(f"Benchmark completed in {elapsed:.3f} seconds")
            
            # Store benchmark result
            with open("benchmark_results.txt", "w") as f:
                f.write(f"Fibonacci(25) benchmark: {elapsed:.3f} seconds\n")
            
            print("✓ Benchmark results saved to benchmark_results.txt")
        
    finally:
        # Clean up
        if os.path.exists("benchmark_temp.tri"):
            os.remove("benchmark_temp.tri")
    
    return success

def clean():
    """Clean build artifacts."""
    print("=" * 50)
    print("Cleaning Build Artifacts")
    print("=" * 50)
    
    # Clean Python cache
    import shutil
    
    artifacts = [
        "__pycache__",
        "*.pyc",
        "*.pyo",
        "benchmark_temp.tri",
        ".pytest_cache"
    ]
    
    success = True
    
    # Remove Python cache directories
    for root, dirs, files in os.walk("."):
        for dir_name in dirs[:]:  # Use slice to avoid modifying while iterating
            if dir_name == "__pycache__":
                cache_path = os.path.join(root, dir_name)
                try:
                    shutil.rmtree(cache_path)
                    print(f"Removed: {cache_path}")
                except OSError as e:
                    print(f"Failed to remove {cache_path}: {e}")
                    success = False
                dirs.remove(dir_name)
    
    # Remove compiled Python files
    for root, dirs, files in os.walk("."):
        for file_name in files:
            if file_name.endswith((".pyc", ".pyo")):
                file_path = os.path.join(root, file_name)
                try:
                    os.remove(file_path)
                    print(f"Removed: {file_path}")
                except OSError as e:
                    print(f"Failed to remove {file_path}: {e}")
                    success = False
    
    if success:
        print("✓ Cleanup completed")
    else:
        print("✗ Some cleanup operations failed")
    
    return success

def install_deps():
    """Install development dependencies."""
    print("=" * 50)
    print("Installing Development Dependencies")
    print("=" * 50)
    
    dependencies = [
        "flake8",
        "black", 
        "pytest",
        "coverage"
    ]
    
    success = True
    for dep in dependencies:
        cmd_success = run_command([sys.executable, "-m", "pip", "install", dep],
                                 f"Install {dep}")
        success = success and cmd_success
    
    return success

def ci():
    """Run continuous integration pipeline."""
    print("=" * 60)
    print("TRION CONTINUOUS INTEGRATION PIPELINE")
    print("=" * 60)
    
    steps = [
        ("Clean", clean),
        ("Lint", lint), 
        ("Test", test),
        ("Benchmark", benchmark),
    ]
    
    all_success = True
    
    for step_name, step_func in steps:
        print(f"\n{'=' * 20} {step_name} {'=' * 20}")
        success = step_func()
        all_success = all_success and success
        
        if not success:
            print(f"❌ CI FAILED at step: {step_name}")
            return False
        
        print(f"✅ {step_name} completed successfully")
    
    if all_success:
        print("\n" + "=" * 60)
        print("🎉 CONTINUOUS INTEGRATION PASSED!")
        print("=" * 60)
    
    return all_success

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Trion Language Build System")
    parser.add_argument("command", choices=[
        "test", "lint", "format", "clean", "benchmark", "ci", "install-deps"
    ], help="Build command to run")
    
    args = parser.parse_args()
    
    # Change to script directory
    os.chdir(Path(__file__).parent)
    
    # Run command
    commands = {
        "test": test,
        "lint": lint,
        "format": format_code,
        "clean": clean,
        "benchmark": benchmark,
        "ci": ci,
        "install-deps": install_deps,
    }
    
    success = commands[args.command]()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()