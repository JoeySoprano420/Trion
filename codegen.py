# codegen.py
"""
Simple LLVM IR code generator for Trion AST using llvmlite.
- Emits one LLVM function per Capsule (named `capsule_<name>`)
- Emits a `main` function that calls capsule functions in AST order
- Recognizes simple `Print` statements in capsule bodies and lowers them to `puts` calls
- Interns string constants as LLVM global constant arrays

This stays intentionally small and easy to extend (expressions, types, externs, etc).
"""

from llvmlite import ir
from typing import Dict, Any
import re

_VALID_NAME = re.compile(r'[^0-9A-Za-z_]')


def _sanitize_name(name: str) -> str:
    if not name:
        return "anon"
    return _VALID_NAME.sub('_', name)


class Codegen:
    def __init__(self, module_name: str = "trion"):
        self.module = ir.Module(name=module_name)
        self.builder: ir.IRBuilder = None  # set when emitting function bodies
        self._str_constants: Dict[str, ir.GlobalVariable] = {}
        self._capsule_funcs: Dict[str, ir.Function] = {}
        self._puts = None  # declared puts function

    # --- helpers for externs and string constants ---

    def _ensure_puts(self):
        if self._puts is not None:
            return
        # declare: int puts(i8*)
        puts_ty = ir.FunctionType(ir.IntType(32), [ir.PointerType(ir.IntType(8))])
        self._puts = ir.Function(self.module, puts_ty, name="puts")

    def _intern_string(self, text: str) -> ir.GlobalVariable:
        """
        Return (and create if needed) a global constant holding `text\0`.
        """
        if text in self._str_constants:
            return self._str_constants[text]
        data = text.encode("utf8") + b"\x00"
        arr_ty = ir.ArrayType(ir.IntType(8), len(data))
        # initializer expects a bytes-like or list of ints
        init = ir.Constant(arr_ty, bytearray(data))
        gv_name = f".str{len(self._str_constants)}"
        gv = ir.GlobalVariable(self.module, arr_ty, name=gv_name)
        gv.global_constant = True
        gv.linkage = "internal"
        gv.initializer = init
        self._str_constants[text] = gv
        return gv

    def _cstr_ptr(self, gv: ir.GlobalVariable) -> ir.Value:
        """
        Return i8* pointer to the first element of the global array.
        """
        ptr_ty = ir.PointerType(ir.IntType(8))
        zero = ir.Constant(ir.IntType(32), 0)
        gep = gv.gep([zero, zero])
        return gep.bitcast(ptr_ty)

    # --- emission routines ---

    def emit_capsule(self, capsule: Any) -> ir.Function:
        """
        Emit a void function for the given Capsule AST node.
        Capsule.body is expected to be an iterable of simple statements (strings or nodes).
        Returns the created Function.
        """
        name = _sanitize_name(getattr(capsule, "name", "capsule"))
        func_name = f"capsule_{name}"
        if func_name in self._capsule_funcs:
            return self._capsule_funcs[func_name]

        func_ty = ir.FunctionType(ir.VoidType(), [])
        func = ir.Function(self.module, func_ty, name=func_name)
        block = func.append_basic_block("entry")
        builder = ir.IRBuilder(block)

        # ensure puts is declared if we will use prints
        self._ensure_puts()

        # naive lowering for string-style statements "Print: ...", "Print ..."
        for stmt in getattr(capsule, "body", []):
            if not isinstance(stmt, str):
                continue
            text = stmt.strip()
            # support "Print:" or "Print"
            if text.lower().startswith("print"):
                # find content after colon if present
                content = ""
                if ":" in text:
                    content = text.split(":", 1)[1].strip()
                else:
                    # "Print foo" -> content after whitespace
                    parts = text.split(None, 1)
                    content = parts[1].strip() if len(parts) > 1 else ""
                # strip matching surrounding quotes
                if len(content) >= 2 and ((content[0] == '"' and content[-1] == '"') or (content[0] == "'" and content[-1] == "'")):
                    content = content[1:-1]
                # fallback for empty prints
                if content == "":
                    content = "\n"
                gv = self._intern_string(content)
                ptr = self._cstr_ptr(gv)
                builder.call(self._puts, [ptr])
            # other stmt kinds may be extended here

        builder.ret_void()
        self._capsule_funcs[func_name] = func
        return func

    def emit_main(self, program: Any):
        """
        Emit a `main` function that calls capsule functions in the order they appear
        in program.body. If a MainBlock node exists it will be emitted as an empty function
        and called as well to maintain ordering.
        """
        func_ty = ir.FunctionType(ir.IntType(32), [])
        main_fn = ir.Function(self.module, func_ty, name="main")
        block = main_fn.append_basic_block("entry")
        self.builder = ir.IRBuilder(block)

        # Emit all capsule functions first
        calls = []
        for node in getattr(program, "body", []):
            tname = type(node).__name__
            if tname == "Capsule":
                fn = self.emit_capsule(node)
                calls.append(fn)
            elif tname == "Main" or tname == "MainBlock":
                # create an empty helper function for MainBlock for symmetry
                mainblk_name = "main_block"
                if mainblk_name not in self._capsule_funcs:
                    fb = ir.Function(self.module, ir.FunctionType(ir.VoidType(), []), name=mainblk_name)
                    b = fb.append_basic_block("entry")
                    ir.IRBuilder(b).ret_void()
                    self._capsule_funcs[mainblk_name] = fb
                calls.append(self._capsule_funcs[mainblk_name])
            else:
                # unknown top-level node: attempt to emit if it has a `name` attr and body
                if hasattr(node, "name") and hasattr(node, "body"):
                    calls.append(self.emit_capsule(node))

        # Call each capsule/function in order
        for fn in calls:
            self.builder.call(fn, [])

        # return 0
        self.builder.ret(ir.Constant(ir.IntType(32), 0))
        self.builder = None
        return main_fn

    def generate(self, program: Any):
        """
        Top-level entry: generate module contents for a Program AST node.
        """
        # clear any previously interned constants to keep names stable per run
        self._str_constants.clear()
        self._capsule_funcs.clear()
        # Produce capsules and main
        for node in getattr(program, "body", []):
            if type(node).__name__ == "Capsule":
                self.emit_capsule(node)
        self.emit_main(program)

    def save(self, path: str = "output.ll"):
        """
        Write the textual IR to `path`.
        """
        with open(path, "w", encoding="utf-8") as f:
            f.write(str(self.module))
            print(f"LLVM IR written to {path}")

