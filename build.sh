#!/bin/bash
echo "🔧 Building Trion to LLVM → EXE"
python3 main.py tests/hello_world.trn
llc output.ll -filetype=obj -o output.o
clang output.o -o hello.exe
