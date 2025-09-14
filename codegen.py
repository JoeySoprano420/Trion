# codegen.py
from llvmlite import ir

class Codegen:
    def __init__(self):
        self.module = ir.Module(name="trion")
        self.builder = None

    def emit_main(self):
        func_ty = ir.FunctionType(ir.VoidType(), [])
        func = ir.Function(self.module, func_ty, name="main")
        block = func.append_basic_block(name="entry")
        self.builder = ir.IRBuilder(block)
        self.builder.ret_void()

    def save(self, path="output.ll"):
        with open(path, "w") as f:
            f.write(str(self.module))
