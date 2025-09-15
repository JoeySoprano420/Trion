# trion_runtime.py
# Python translation of trion_runtime.c (portable, best-effort feature parity)
# Note: This is a high-level port; low-level behaviors (memory, seccomp, dlopen) are adapted to Python.
# Author: GitHub Copilot (translated)
# License: MIT-style permissive (use per project license)

from __future__ import annotations
import threading
import time
import os
import tempfile
import shutil
import subprocess
import ctypes
import json
from collections import deque
from typing import Optional, Callable, Any, Tuple

# ---------------------------
# Internal error / audit logging helpers
# ---------------------------

_tls = threading.local()
_tls.last_error_msg = ""

_error_lock = threading.Lock()
_audit_lock = threading.Lock()
_audit_fp = None  # file-like or None

def tr_set_last_error_fmt(fmt: str, *args) -> None:
    msg = fmt % args if args else fmt
    with _error_lock:
        _tls.last_error_msg = msg

def tr_get_last_error() -> str:
    with _error_lock:
        return getattr(_tls, "last_error_msg", "") or ""

def tr_audit_open(path: str) -> int:
    global _audit_fp
    try:
        with _audit_lock:
            if _audit_fp:
                _audit_fp.close()
            _audit_fp = open(path, "a", buffering=1)
        return 0
    except Exception as e:
        tr_set_last_error_fmt("audit_open: failed to open %s: %s", path, str(e))
        return -1

def tr_audit_close() -> None:
    global _audit_fp
    with _audit_lock:
        if _audit_fp:
            _audit_fp.close()
            _audit_fp = None

def tr_audit_log(fmt: str, *args) -> None:
    msg = fmt % args if args else fmt
    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    with _audit_lock:
        if _audit_fp:
            _audit_fp.write(f"[{ts}] {msg}\n")
        else:
            # fallback to stderr
            print(f"[audit] {msg}", flush=True)

# ---------------------------
# Quarantine (simple ownership tracker)
# ---------------------------

class Quarantine:
    def __init__(self, initial_capacity: int = 16):
        self._items: list = []
        self._sealed = False
        self._lock = threading.Lock()

    def alloc(self, size: int) -> bytearray:
        if size <= 0:
            tr_set_last_error_fmt("quarantine_alloc: invalid args")
            return None
        with self._lock:
            if self._sealed:
                tr_set_last_error_fmt("quarantine_alloc: quarantined sealed")
                return None
            buf = bytearray(size)
            self._items.append(buf)
            return buf

    def free(self, obj) -> int:
        if obj is None:
            tr_set_last_error_fmt("quarantine_free: invalid args")
            return -1
        with self._lock:
            try:
                self._items.remove(obj)
                return 0
            except ValueError:
                tr_set_last_error_fmt("quarantine_free: pointer not found")
                return -1

    def seal(self) -> None:
        with self._lock:
            self._sealed = True

    def destroy(self) -> None:
        with self._lock:
            self._items.clear()

    def strdup(self, s: str) -> str:
        # Python strings are immutable; keep reference in quarantine for semantics
        with self._lock:
            self._items.append(s)
            return s

# ---------------------------
# Channel (bounded, blocking/non-blocking/timed)
# ---------------------------

class Channel:
    def __init__(self, capacity: int):
        if capacity <= 0:
            raise ValueError("channel_create: invalid capacity")
        self._buf = deque(maxlen=capacity)
        self._capacity = capacity
        self._lock = threading.Lock()
        self._not_empty = threading.Condition(self._lock)
        self._not_full = threading.Condition(self._lock)
        self._closed = False

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._not_empty.notify_all()
            self._not_full.notify_all()

    def destroy(self) -> None:
        with self._lock:
            self._buf.clear()

    # return codes: 0 = success, -1 = closed/error, -2 = would block, -3 = timeout
    def send(self, item, blocking: bool = True, timeout_ms: int = 0) -> int:
        with self._lock:
            if self._closed:
                tr_set_last_error_fmt("channel_send: closed")
                return -1
            if not blocking and len(self._buf) >= self._capacity:
                tr_set_last_error_fmt("channel_send: would block")
                return -2
            start = time.monotonic()
            while len(self._buf) >= self._capacity:
                if not blocking:
                    tr_set_last_error_fmt("channel_send: would block")
                    return -2
                if timeout_ms == 0:
                    self._not_full.wait()
                else:
                    remaining = timeout_ms / 1000.0 - (time.monotonic() - start)
                    if remaining <= 0 or not self._not_full.wait(timeout=remaining):
                        tr_set_last_error_fmt("channel_send: timeout")
                        return -3
                if self._closed:
                    tr_set_last_error_fmt("channel_send: closed during wait")
                    return -1
            self._buf.append(item)
            self._not_empty.notify()
            return 0

    # recv returns tuple (code, item)
    # code: 1 = item returned, 0 = closed and no item, -1 = invalid args, -2 = would block, -3 = timeout
    def recv(self, blocking: bool = True, timeout_ms: int = 0) -> Tuple[int, Optional[Any]]:
        with self._lock:
            if not blocking and len(self._buf) == 0:
                if self._closed:
                    return 0, None
                tr_set_last_error_fmt("channel_recv: would block")
                return -2, None
            start = time.monotonic()
            while len(self._buf) == 0:
                if self._closed:
                    return 0, None
                if not blocking:
                    tr_set_last_error_fmt("channel_recv: would block")
                    return -2, None
                if timeout_ms == 0:
                    self._not_empty.wait()
                else:
                    remaining = timeout_ms / 1000.0 - (time.monotonic() - start)
                    if remaining <= 0 or not self._not_empty.wait(timeout=remaining):
                        tr_set_last_error_fmt("channel_recv: timeout")
                        return -3, None
            item = self._buf.popleft()
            self._not_full.notify()
            return 1, item

# ---------------------------
# Thread wrappers (simple)
# ---------------------------

def tr_thread_create(fn: Callable[[Any], Any], arg: Any) -> threading.Thread:
    t = threading.Thread(target=fn, args=(arg,), daemon=False)
    t.start()
    return t

def tr_thread_join(t: threading.Thread) -> int:
    if not t:
        tr_set_last_error_fmt("tr_thread_join: invalid thread")
        return -1
    t.join()
    return 0

# ---------------------------
# Dodecagram (base-12) helpers (uint64)
# ---------------------------

_DG_DIGITS = "0123456789ab"
_DG_MAP = {c: i for i, c in enumerate(_DG_DIGITS)}
_DG_MAP.update({'A': 10, 'B': 11})

def tr_to_base12_u64(n: int) -> Optional[str]:
    if n is None:
        tr_set_last_error_fmt("tr_to_base12_u64: invalid args")
        return None
    if n == 0:
        return "0"
    neg = n < 0
    if neg:
        n = -n
    digits = []
    while n:
        digits.append(_DG_DIGITS[n % 12])
        n //= 12
    s = ''.join(reversed(digits))
    return '-' + s if neg else s

def tr_from_base12_u64(s: str) -> Optional[int]:
    if s is None:
        tr_set_last_error_fmt("tr_from_base12_u64: invalid args")
        return None
    s = s.strip()
    if s == "":
        tr_set_last_error_fmt("tr_from_base12_u64: invalid args")
        return None
    neg = False
    if s[0] in '+-':
        if s[0] == '-':
            neg = True
        s = s[1:]
    val = 0
    for c in s:
        if c in ('_', ' '):
            continue
        if c.isdigit():
            d = ord(c) - ord('0')
        elif c in ('a', 'A'):
            d = 10
        elif c in ('b', 'B'):
            d = 11
        else:
            tr_set_last_error_fmt("tr_from_base12_u64: invalid digit '%s'", c)
            return None
        # overflow check top-level: Python ints are unbounded, but replicate semantics loosely
        val = val * 12 + d
    return -val if neg else val

# ---------------------------
# Bytes <-> base12 (arbitrary length)
# ---------------------------

def bytes_to_base12(b: bytes) -> str:
    if not b:
        return "0"
    n = int.from_bytes(b, byteorder='big', signed=False)
    return tr_to_base12_u64(n)

def bytes_to_base12_scaled(b: bytes, scale: int) -> Optional[str]:
    if scale < 0:
        tr_set_last_error_fmt("bytes_to_base12_scaled: negative scale")
        return None
    s = bytes_to_base12(b)
    if scale == 0:
        return s
    # ensure at least scale+1 digits by left padding with zeros
    if len(s) <= scale:
        need = scale + 1 - len(s)
        return "0." + ("0" * need) + s
    else:
        intpart = s[:-scale]
        fracpart = s[-scale:]
        return f"{intpart}.{fracpart}"

def base12_to_bytes_with_scale(s: str) -> Optional[Tuple[bytes, int]]:
    if s is None:
        tr_set_last_error_fmt("base12_to_bytes_with_scale: invalid args")
        return None
    s = s.strip()
    if s == "":
        tr_set_last_error_fmt("base12_to_bytes_with_scale: invalid args")
        return None
    neg = False
    if s[0] in '+-':
        if s[0] == '-': neg = True
        s = s[1:]
    if '.' in s:
        int_part, frac_part = s.split('.', 1)
    else:
        int_part, frac_part = s, ""
    digits = []
    for c in (int_part + frac_part):
        if c in ('_', ' '):
            continue
        if c.isdigit():
            d = ord(c) - ord('0')
        elif c in ('a', 'A'):
            d = 10
        elif c in ('b', 'B'):
            d = 11
        else:
            tr_set_last_error_fmt("base12_to_bytes_with_scale: invalid digit '%s'", c)
            return None
        digits.append(d)
    # compute integer value as big int
    val = 0
    for d in digits:
        val = val * 12 + d
    scale = len(frac_part)
    # convert to minimal bytes big-endian
    if val == 0:
        out = b"\x00"
    else:
        blen = (val.bit_length() + 7) // 8
        out = val.to_bytes(blen, byteorder='big', signed=False)
    # sign is not encoded in bytes; caller should track sign separately if needed
    return out, scale

def base12_to_bytes(s: str) -> Optional[bytes]:
    res = base12_to_bytes_with_scale(s)
    if not res:
        return None
    out, _scale = res
    return out

# ---------------------------
# Packet helpers
# ---------------------------

class TrionPacket:
    def __init__(self, q: Quarantine, payload: Optional[bytes] = None):
        if q is None:
            tr_set_last_error_fmt("tr_packet_create: invalid quarantine")
            raise ValueError("invalid quarantine")
        self.q = q
        self.payload = None
        self.length = 0
        if payload:
            buf = q.alloc(len(payload))
            if buf is None:
                tr_set_last_error_fmt("tr_packet_create: quarantine_alloc failed")
                raise MemoryError("quarantine alloc failed")
            # copy payload into quarantine-owned bytearray
            buf[:len(payload)] = payload
            self.payload = buf
            self.length = len(payload)
        self.src_ip = 0
        self.dst_ip = 0
        self.src_port = 0
        self.dst_port = 0

    def destroy(self) -> None:
        # user should free payload via quarantine.free if desired; here just drop reference
        self.payload = None

def tr_packet_drop_if_src_ip(p: TrionPacket, ip: int) -> bool:
    if not p:
        return False
    return p.src_ip == ip

# ---------------------------
# Capsule lifecycle, messaging and callbacks
# ---------------------------

class Capsule:
    def __init__(self, name: str, entry: Optional[Callable[['Capsule', Any], int]] = None, user_ctx: Any = None):
        if not name:
            tr_set_last_error_fmt("tr_capsule_create: invalid name")
            raise ValueError("invalid name")
        self.q = Quarantine(16)
        self.name = self.q.strdup(name)
        self.inbox = Channel(32)
        self.thread: Optional[threading.Thread] = None
        self.running = False
        self.user_ctx = user_ctx
        self.entry = entry

    def _thread_main(self):
        self.running = True
        if _global_callback_registry:
            _global_callback_registry.emit(self, "capsule_start")
        rc = 0
        try:
            if self.entry:
                rc = self.entry(self, self.user_ctx) or 0
            # drain inbox (non-blocking)
            while True:
                code, msg = self.inbox.recv(blocking=False)
                if code != 1:
                    break
        except Exception as e:
            tr_audit_log("capsule exception: %s", str(e))
        finally:
            self.running = False
            if _global_callback_registry:
                _global_callback_registry.emit(self, "capsule_stop")
        return rc

    def start(self) -> int:
        if self.running:
            tr_set_last_error_fmt("tr_capsule_start: already running")
            return -1
        self.thread = tr_thread_create(lambda ctx: self._thread_main(), None)
        return 0

    def join(self) -> int:
        if not self.thread:
            return 0
        return tr_thread_join(self.thread)

    def send(self, msg) -> int:
        if not self.inbox:
            tr_set_last_error_fmt("tr_capsule_send: invalid args")
            return -1
        return self.inbox.send(msg, blocking=True)

    def try_send(self, msg) -> int:
        if not self.inbox:
            tr_set_last_error_fmt("tr_capsule_try_send: invalid args")
            return -1
        return self.inbox.send(msg, blocking=False)

    def destroy(self) -> None:
        if self.running:
            if self.inbox:
                self.inbox.close()
            if self.thread:
                tr_thread_join(self.thread)
        if self.inbox:
            self.inbox.destroy()
        self.q.destroy()

# ---------------------------
# Callback registry
# ---------------------------

class CallbackRegistry:
    def __init__(self):
        self._callbacks: list[Tuple[Callable[[Capsule, str, Any], None], Any]] = []
        self._lock = threading.Lock()

    def register(self, cb: Callable[[Capsule, str, Any], None], ctx: Any = None) -> int:
        if not cb:
            tr_set_last_error_fmt("tr_register_event_callback: invalid cb")
            return -1
        with self._lock:
            self._callbacks.append((cb, ctx))
        return 0

    def emit(self, capsule: Capsule, evt: str) -> None:
        with self._lock:
            items = list(self._callbacks)
        for cb, ctx in items:
            try:
                cb(capsule, evt, ctx)
            except Exception as e:
                tr_audit_log("callback exception: %s", str(e))

_global_callback_registry: Optional[CallbackRegistry] = CallbackRegistry()

def tr_register_event_callback(cb: Callable[[Capsule, str, Any], None], ctx: Any = None) -> int:
    if not _global_callback_registry:
        return -1
    return _global_callback_registry.register(cb, ctx)

# ---------------------------
# Timer helpers (single-shot)
# ---------------------------

def tr_timer_start(ms: int, cb: Callable[[Any], None], ctx: Any) -> int:
    if not cb:
        tr_set_last_error_fmt("tr_timer_start: invalid callback")
        return -1
    def _fn(_ctx):
        time.sleep(ms / 1000.0)
        try:
            cb(ctx)
        except Exception as e:
            tr_audit_log("timer callback error: %s", str(e))
    t = threading.Thread(target=_fn, args=(ctx,), daemon=True)
    t.start()
    return 0

# ---------------------------
# Syscall registry
# ---------------------------

class SyscallEntry:
    def __init__(self, name: str, handler: Callable[[Optional[str], Any], Tuple[int, Optional[str]]],
                 ctx: Any = None, flags: int = 0, auth_token: Optional[str] = None, description: Optional[str] = None):
        self.name = name
        self.handler = handler
        self.ctx = ctx
        self.flags = flags
        self.auth_token = auth_token
        self.description = description

class SyscallRegistry:
    def __init__(self):
        self._entries: dict[str, SyscallEntry] = {}
        self._lock = threading.Lock()

    def register_ex(self, name: str, handler: Callable[[Optional[str], Any], Tuple[int, Optional[str]]],
                    ctx: Any = None, flags: int = 0, auth_token: Optional[str] = None,
                    description: Optional[str] = None) -> int:
        if not name or not handler:
            tr_set_last_error_fmt("tr_register_syscall_ex: invalid args")
            return -1
        with self._lock:
            self._entries[name] = SyscallEntry(name, handler, ctx, flags, auth_token, description)
        tr_audit_log("syscall_registered: %s flags=%d desc=%s", name, flags, description or "")
        return 0

    def unregister(self, name: str) -> int:
        if not name:
            tr_set_last_error_fmt("tr_unregister_syscall: invalid name")
            return -1
        with self._lock:
            if name in self._entries:
                del self._entries[name]
                tr_audit_log("syscall_unregistered: %s", name)
                return 0
        tr_set_last_error_fmt("tr_unregister_syscall: not found")
        return -1

    def invoke_ex(self, name: str, args_json: Optional[str], auth_token: Optional[str]) -> Tuple[int, Optional[str]]:
        if not name:
            tr_set_last_error_fmt("tr_invoke_syscall_ex: invalid name")
            return -1, None
        with self._lock:
            entry = self._entries.get(name)
        if not entry:
            tr_set_last_error_fmt("tr_invoke_syscall_ex: not found")
            return -3, None
        if entry.auth_token:
            if not auth_token or auth_token != entry.auth_token:
                tr_set_last_error_fmt("tr_invoke_syscall_ex: auth failed for %s", name)
                tr_audit_log("syscall_invoke_failed_auth: %s", name)
                return -4, None
        audit = (entry.flags & 1) != 0
        if audit:
            tr_audit_log("syscall_invoke: %s args=%s", name, args_json or "null")
        try:
            rc, out = entry.handler(args_json, entry.ctx)
        except Exception as e:
            tr_set_last_error_fmt("syscall handler %s exception: %s", name, str(e))
            rc, out = -1, None
        if audit:
            tr_audit_log("syscall_invoke_result: %s rc=%d out=%s", name, rc, out or "null")
        if rc != 0 and not tr_get_last_error():
            tr_set_last_error_fmt("syscall handler %s returned %d", name, rc)
        return rc, out

_syscall_registry = SyscallRegistry()

def tr_register_syscall_ex(name, handler, ctx=None, flags=0, auth_token=None, description=None):
    return _syscall_registry.register_ex(name, handler, ctx, flags, auth_token, description)

def tr_unregister_syscall(name):
    return _syscall_registry.unregister(name)

def tr_invoke_syscall_ex(name, args_json, auth_token=None):
    return _syscall_registry.invoke_ex(name, args_json, auth_token)

# ---------------------------
# Sandbox runner (best-effort)
# ---------------------------

def tr_try_harden_child(run_uid: Optional[int], run_gid: Optional[int]) -> None:
    # Best-effort: try to drop privileges and set resource limits can be done in preexec_fn
    tr_audit_log("sandbox: attempting to harden child (python-best-effort)")

def tr_sandbox_run(path: str, argv: Optional[list] = None, envp: Optional[dict] = None,
                   working_dir: Optional[str] = None, time_ms: int = 0, memory_limit_bytes: int = 0,
                   run_uid: Optional[int] = None, run_gid: Optional[int] = None) -> Tuple[int, Optional[int]]:
    if not path:
        tr_set_last_error_fmt("tr_sandbox_run: path is NULL")
        return -1, None
    argv = argv or [path]
    envp = envp or os.environ.copy()

    def preexec():
        # run in child process (Unix only)
        try:
            if run_gid is not None:
                os.setgid(run_gid)
            if run_uid is not None:
                os.setuid(run_uid)
            if memory_limit_bytes and hasattr(__import__('resource'), 'setrlimit'):
                import resource
                resource.setrlimit(resource.RLIMIT_AS, (memory_limit_bytes, memory_limit_bytes))
            if time_ms and hasattr(__import__('resource'), 'setrlimit'):
                import resource
                cpu_sec = (time_ms + 999) // 1000
                resource.setrlimit(resource.RLIMIT_CPU, (cpu_sec, cpu_sec))
            # attempt os.unshare if available (Linux)
            if hasattr(os, 'unshare'):
                flags = 0
                # try to unshare new ns if constants exist
                for name in ('CLONE_NEWPID', 'CLONE_NEWNS', 'CLONE_NEWNET'):
                    val = getattr(os, name, None)
                    if val:
                        flags |= val
                if flags:
                    try:
                        os.unshare(flags)
                        tr_audit_log("sandbox: unshare succeeded flags=%d", flags)
                    except Exception as e:
                        tr_audit_log("sandbox: unshare failed: %s", str(e))
        except Exception as e:
            # Can't really set last error here (child)
            tr_audit_log("sandbox preexec failed: %s", str(e))

    try:
        proc = subprocess.Popen(argv, cwd=working_dir, env=envp, preexec_fn=preexec if os.name != 'nt' else None)
        try:
            timeout = None if time_ms == 0 else (time_ms / 1000.0)
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            tr_set_last_error_fmt("tr_sandbox_run: timeout, killed child")
            tr_audit_log("sandbox_run: timeout pid=%d path=%s", proc.pid, path)
            return -2, -1
        returncode = proc.returncode
        if returncode < 0:
            # terminated by signal on Unix
            return -3, -abs(returncode)
        return 0, returncode
    except Exception as e:
        tr_set_last_error_fmt("tr_sandbox_run: failed: %s", str(e))
        return -1, None

# ---------------------------
# JIT / NASM bridging (best-effort via clang/nasm and ctypes)
# ---------------------------

def tr_nasm_compile_and_load(nasm_src: str, entry_symbol: str) -> Tuple[int, Optional[ctypes.CFUNCTYPE], Optional[str]]:
    """
    Attempts to compile assembly using clang (preferred), or nasm+clang/gcc fallback.
    On success returns (0, callable pointer, None). On error returns (errcode, None, err_msg).
    """
    if not nasm_src or not entry_symbol:
        tr_set_last_error_fmt("tr_nasm_compile_and_load: invalid args")
        return -1, None, "invalid arguments"
    tmpdir = tempfile.mkdtemp(prefix="trion_nasm_")
    asm_path = os.path.join(tmpdir, "module.asm")
    obj_path = os.path.join(tmpdir, "module.o")
    so_path = os.path.join(tmpdir, "module.so")
    log_path = os.path.join(tmpdir, "build.log")
    try:
        with open(asm_path, "wb") as f:
            f.write(nasm_src.encode('utf-8'))
        used_clang = False
        # try clang assembling assembly file directly
        clang = shutil.which("clang")
        gcc = shutil.which("gcc")
        nasm = shutil.which("nasm")
        def run(cmd):
            with open(log_path, "ab") as lf:
                res = subprocess.call(cmd, shell=True, stdout=lf, stderr=lf)
            return res
        r = 1
        if clang:
            r = run(f'clang -c -x assembler "{asm_path}" -o "{obj_path}" 2>> "{log_path}"')
            if r == 0:
                used_clang = True
                r = run(f'clang -shared -fPIC -o "{so_path}" "{obj_path}" 2>> "{log_path}"')
        if r != 0 and nasm:
            r = run(f'nasm -f elf64 "{asm_path}" -o "{obj_path}" 2>> "{log_path}"')
            if r == 0:
                linker = "clang" if shutil.which("clang") else ("gcc" if gcc else None)
                if not linker:
                    r = 1
                else:
                    r = run(f'{linker} -shared -fPIC -o "{so_path}" "{obj_path}" 2>> "{log_path}"')
        if r != 0:
            # read log
            try:
                with open(log_path, "rb") as lf:
                    data = lf.read().decode('utf-8', errors='replace')
                errmsg = data + f"\nCommand failed. Clang used={int(used_clang)}"
            except Exception:
                errmsg = "build failed and no log available"
            tr_set_last_error_fmt("tr_nasm_compile_and_load: build failed; see err_msg")
            return -2, None, errmsg
        # load via ctypes
        try:
            lib = ctypes.CDLL(so_path)
            sym = getattr(lib, entry_symbol, None)
            if sym is None:
                tr_set_last_error_fmt("tr_nasm_compile_and_load: symbol not found")
                return -5, None, "dlsym failed"
            tr_audit_log("jit_load: compiled and loaded %s entry=%s", asm_path, entry_symbol)
            return 0, sym, None
        except Exception as e:
            tr_set_last_error_fmt("tr_nasm_compile_and_load: dlopen/dlsym failed: %s", str(e))
            return -4, None, str(e)
    finally:
        # leave tmpdir for inspection in case of failure; user can cleanup
        pass

# ---------------------------
# Utility debug helpers
# ---------------------------

def tr_log(fmt: str, *args) -> None:
    print(fmt % args if args else fmt)

# End of trion_runtime.py
