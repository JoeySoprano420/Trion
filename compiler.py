"""
lexer.py

Tokenizer for Trion language.

Produces a list of (type, value) tuples suitable for the simple parser.
Ignores whitespace, comments and newlines. Keywords are matched before identifiers.
"""

import re
from typing import List, Tuple

# Ordered token specs: order matters (KEYWORD before IDENT)
TOKEN_SPECS = [
    ("SKIP",     r"[ \t\r]+"),                             # spaces and tabs
    ("COMMENT",  r"--[^\n]*"),                             # -- comment to end of line
    ("NEWLINE",  r"\n"),                                   # newline
    ("KEYWORD",  r"\b(?:Main|Capsule|If|Then|Else|Elseif|While|For|EndCapsule|Print|Isolate|Try|Execute|Fail|True|False)\b"),
    ("IDENT",    r"[A-Za-z_][A-Za-z0-9_]*"),               # identifiers
    ("NUMBER",   r"\b\d+\b"),                              # integers
    ("STRING",   r'"(?:\\.|[^"\\])*"'),                    # double-quoted strings with escapes
    ("OP",       r"[+\-*/<>=,:]"),                         # operators / punctuation
    ("MISMATCH", r"."),                                    # any other single char
]

# Precompile regexes for performance
_TOKEN_REGEXES = [(typ, re.compile(pattern)) for typ, pattern in TOKEN_SPECS]


def tokenize(code: str) -> List[Tuple[str, str]]:
    """
    Tokenize Trion source `code` and return list of (type, value) tuples.

    Whitespace, comments and newline tokens are ignored (not returned).
    """
    tokens: List[Tuple[str, str]] = []
    pos = 0
    length = len(code)

    while pos < length:
        for typ, regex in _TOKEN_REGEXES:
            m = regex.match(code, pos)
            if not m:
                continue
            text = m.group(0)
            pos = m.end()
            # skip these token types
            if typ in ("SKIP", "COMMENT", "NEWLINE"):
                break
            tokens.append((typ, text))
            break
        else:
            # Should not happen because MISMATCH will always match; safety fallback
            tokens.append(("MISMATCH", code[pos]))
            pos += 1

    return tokens


if __name__ == "__main__":
    # quick smoke test
    sample = '''
    Main ()
    Capsule Greeter
        Print: "Hello, Trion"
    EndCapsule
    -- a comment
    '''
    for t in tokenize(sample):
        print(t)

from typing import Any, List, Optional, Tuple
from ast import (
    Program as AstProgram,
    MainBlock as AstMainBlock,
    Capsule as AstCapsule,
    RawStmt,
    PrintStmt,
    RuleStmt,
)

"""
parser.py

Parser-local thin AST subclasses and the Parser implementation.

The parser-local Program/MainBlock/Capsule classes are thin, fully-implemented
subclasses of the canonical AST nodes from ast.py. They keep the parser's
legacy behaviour (storing raw statement strings) while offering helpers to
convert body entries to structured statement nodes when needed.

This file intentionally keeps the Parser simple and tolerant: it produces a
usable AST for the rest of the toolchain and provides `to_structured()` helpers
so downstream passes can opt into a structured representation without breaking
backwards compatibility with existing codegen that expects raw strings.
"""


class Program(AstProgram):
    """Parser-local Program node (subclass of ast.Program)."""

    def __init__(self, body: Optional[List[Any]] = None, lineno: Optional[int] = None):
        super().__init__(body=body, lineno=lineno)

    def add(self, node: Any) -> None:
        """Append a top-level node."""
        super().add(node)

    def __repr__(self) -> str:
        names = ", ".join(type(n).__name__ for n in self.body)
        return f"Program([{names}])"


class MainBlock(AstMainBlock):
    """Parser-local MainBlock node (subclass of ast.MainBlock)."""

    def __init__(self, body: Optional[List[Any]] = None, lineno: Optional[int] = None):
        super().__init__(body=body, lineno=lineno)

    def add(self, stmt: Any) -> None:
        """Append a statement (string or node)."""
        super().add(stmt)

    def to_structured(self) -> "MainBlock":
        """
        Convert any raw string statements in the body into structured statement
        nodes (PrintStmt / RawStmt). Returns a new MainBlock instance.
        """
        new_body: List[Any] = []
        for item in self.body:
            if isinstance(item, str):
                parsed = _parse_statement_to_node(item)
                new_body.append(parsed)
            else:
                new_body.append(item)
        return MainBlock(body=new_body, lineno=self.lineno)


class Capsule(AstCapsule):
    """Parser-local Capsule node (subclass of ast.Capsule)."""

    def __init__(self, name: str, body: Optional[List[Any]] = None, lineno: Optional[int] = None):
        super().__init__(name=name, body=body, lineno=lineno)

    def add(self, stmt: Any) -> None:
        """
        Add a statement or raw fragment to the capsule body.

        Behaviour:
         - If `stmt` is a Node instance, append as-is.
         - If `stmt` is a str, append the string (legacy behaviour).
        """
        super().add(stmt)

    def to_structured(self) -> "Capsule":
        """
        Convert raw string statements in this capsule's body into structured AST
        statement nodes (PrintStmt, RuleStmt, RawStmt). Returns a new Capsule
        instance with converted body. Does not mutate the original capsule.
        """
        new_body: List[Any] = []
        for item in self.body:
            if isinstance(item, str):
                new_body.append(_parse_statement_to_node(item))
            else:
                new_body.append(item)
        return Capsule(name=self.name, body=new_body, lineno=self.lineno)

    def find_rules(self) -> List[Tuple[int, RuleStmt]]:
        """
        Convenience: return list of (index, RuleStmt) for rule-like text entries.
        The parser may store Rule lines as raw strings; this helper identifies them
        and returns structured RuleStmt objects (without modifying the capsule).
        """
        results: List[Tuple[int, RuleStmt]] = []
        for i, item in enumerate(self.body):
            if isinstance(item, str):
                # heuristics: lines that start with "Rule" (case-insensitive)
                s = item.strip()
                if s.lower().startswith("rule"):
                    rs = RuleStmt(s)
                    results.append((i, rs))
            elif isinstance(item, RuleStmt):
                results.append((i, item))
        return results

    def __repr__(self) -> str:
        return f"Capsule({self.name!r}, stmts={len(self.body)})"


# -------------------------
# Statement parsing helpers
# -------------------------


def _strip_surrounding_quotes(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and ((s[0] == '"' and s[-1] == '"') or (s[0] == "'" and s[-1] == "'")):
        return s[1:-1]
    return s


def _parse_statement_to_node(s: str):
    """
    Heuristic parser for single-line statements produced by the tokenizer/parser.
    Converts a statement string into a structured AST node where possible.

    Heuristics supported:
     - Print: "Print: ..."  or "Print ..." -> PrintStmt with content string
     - Rule:  "Rule: ..."   or "Rule ..."  -> RuleStmt with raw text
     - fallback: RawStmt(original string)
    """
    if not isinstance(s, str):
        return s

    t = s.strip()
    if t == "":
        return RawStmt("")

    lower = t.lower()
    # Print statement detection
    if lower.startswith("print"):
        # extract after colon or whitespace
        content = ""
        if ":" in t:
            content = t.split(":", 1)[1].strip()
        else:
            parts = t.split(None, 1)
            content = parts[1].strip() if len(parts) > 1 else ""
        content = _strip_surrounding_quotes(content)
        return PrintStmt(content)

    # Rule statement detection
    if lower.startswith("rule"):
        # keep full text for RuleStmt
        return RuleStmt(t)

    # Fallback to RawStmt
    return RawStmt(t)


# -------------------------
# Parser implementation
# -------------------------


class Parser:
    def __init__(self, tokens: List[Tuple[str, str]]):
        self.tokens = list(tokens)
        self.pos = 0

    # Main parse loop: walks through all tokens and constructs AST nodes
    def parse(self) -> Program:
        nodes: List[Any] = []
        while not self._eof():
            if self._match("KEYWORD", "Main"):
                nodes.append(self._parse_main())
            elif self._match("KEYWORD", "Capsule"):
                nodes.append(self._parse_capsule())
            else:
                # skip unknown or stray tokens
                self._advance()
        return Program(nodes)

    # Utility helpers
    def _eof(self) -> bool:
        return self.pos >= len(self.tokens)

    def _peek(self) -> Tuple[Optional[str], Optional[str]]:
        if self._eof():
            return (None, None)
        return self.tokens[self.pos]

    def _advance(self) -> Tuple[Optional[str], Optional[str]]:
        if self._eof():
            return (None, None)
        t = self.tokens[self.pos]
        self.pos += 1
        return t

    # Utility to match current token type and optional value
    def _match(self, typ: str, val: Optional[str] = None) -> bool:
        if self._eof():
            return False
        t_type, t_val = self._peek()
        if t_type == typ and (val is None or t_val == val):
            return True
        return False

    # Parse a Main block definition
    def _parse_main(self) -> MainBlock:
        # consume 'Main'
        self._advance()
        # Create MainBlock and collect any following statements until a top-level keyword.
        mb = MainBlock()
        # Collect tokens until we encounter a top-level KEYWORD (Main/Capsule/EndCapsule) or EOF
        while not self._eof():
            t_type, t_val = self._peek()
            if t_type == "KEYWORD" and t_val in ("Main", "Capsule", "EndCapsule"):
                break
            # gather fragments into a single string per line-like statement
            if t_type is None:
                self._advance()
                continue
            # consume contiguous non-KEYWORD tokens as one fragment
            parts: List[str] = []
            while not self._eof() and self._peek()[0] != "KEYWORD":
                tok = self._advance()[1]
                if tok is not None:
                    parts.append(tok)
            frag = " ".join(parts).strip()
            if frag:
                mb.add(frag)
            # if next token is KEYWORD we will break on next loop iteration
        return mb

    # Parse a Capsule declaration with name and a simple list of statements
    def _parse_capsule(self) -> Capsule:
        # consume 'Capsule'
        self._advance()
        # expect identifier for capsule name
        if not self._match("IDENT"):
            # fallback: use a placeholder name and continue
            name = "<anonymous>"
        else:
            _, name = self._advance()

        capsule = Capsule(name)

        # Collect simple statements until EndCapsule is encountered.
        # A statement is heuristically started by a KEYWORD and continues until the next KEYWORD
        # or until EndCapsule. This is intentionally simple and tolerant; more precise parsing
        # can be added later.
        while not self._eof() and not self._match("KEYWORD", "EndCapsule"):
            t_type, t_val = self._peek()
            if t_type == "KEYWORD":
                # start a new statement
                stmt_parts: List[str] = []
                # include the starting keyword (e.g. Print, Rule, Isolate)
                first = self._advance()[1]
                if first is not None:
                    stmt_parts.append(first)
                # consume following non-KEYWORD tokens as part of this statement
                while not self._eof() and self._peek()[0] != "KEYWORD":
                    next_tok = self._advance()[1]
                    if next_tok is not None:
                        stmt_parts.append(next_tok)
                stmt = " ".join(part for part in stmt_parts if part is not None).strip()
                if stmt:
                    capsule.add(stmt)
            else:
                # For non-keyword stray tokens, consume and append as a raw fragment
                frag = self._advance()[1]
                if frag is None:
                    continue
                if len(capsule.body) == 0:
                    capsule.add(frag)
                else:
                    # append to last entry with a space
                    last = capsule.body[-1]
                    if isinstance(last, str):
                        capsule.body[-1] = last + " " + frag
                    else:
                        capsule.add(frag)

        # consume EndCapsule if present
        if self._match("KEYWORD", "EndCapsule"):
            self._advance()

        return capsule


# -------------------------
# Minimal self-test / example
# -------------------------
if __name__ == "__main__":
    from lexer import tokenize
    sample_code = """
    Main
        Print: "Hello, World!"
        Print "This is a test."
    Capsule MyCapsule
        Rule: If condition then action
        Print: "Inside capsule"
    EndCapsule
    Capsule EmptyCapsule
    EndCapsule
    """
    tokens = tokenize(sample_code)
    parser = Parser(tokens)
    ast = parser.parse()
    print(ast)
    for node in ast.body:
        if isinstance(node, MainBlock):
            print("MainBlock:", node.to_structured())
        elif isinstance(node, Capsule):
            print("Capsule:", node.name, node.to_structured())
            rules = node.find_rules()
            for idx, rule in rules:
                print(f"  Found rule at index {idx}: {rule}")

"""
TrionPatternAI.py
Pattern matching and deduction helpers for the Trion compiler.

Provides:
- PatternRule: declarative pattern + optional transformation action
- PatternEngine: register rules, analyze AST, produce suggestions, apply safe transforms

This module is intentionally small, dependency-free and designed to work with the
simple AST classes in `ast.py` (Program, Capsule, MainBlock). Patterns are
simple dictionaries describing node types and attribute constraints.

Example usage:
    from ast import Program, Capsule
    engine = PatternEngine()
    engine.register_rule(remove_empty_capsule_rule)
    program = Program([ Capsule("Empty") ])
    suggestions = engine.analyze(program)
    engine.apply_transforms(program)
"""

from typing import Any, Callable, Dict, List, Optional, Tuple
import inspect

# Types
Pattern = Dict[str, Any]
Action = Callable[[Any], Optional[Any]]  # action(node) -> replacement or None


class PatternRule:
    def __init__(self, name: str, pattern: Pattern, action: Optional[Action] = None, description: str = ""):
        """
        pattern: {
            "__type__": "Capsule",         # optional: class name to match
            "attrs": { "name": "Foo" },    # optional: attribute name -> expected or callable
        }
        action: function that receives the matched node and returns:
                - None to indicate no structural replacement (only suggestion)
                - a new node to replace the matched node
        """
        self.name = name
        self.pattern = pattern
        self.action = action
        self.description = description

    def matches(self, node: Any) -> bool:
        # Match type
        t = self.pattern.get("__type__")
        if t:
            if type(node).__name__ != t:
                return False
        # Match attributes
        attrs = self.pattern.get("attrs", {})
        for k, expected in attrs.items():
            if not hasattr(node, k):
                return False
            val = getattr(node, k)
            if callable(expected):
                try:
                    if not expected(val):
                        return False
                except Exception:
                    return False
            else:
                if val != expected:
                    return False
        return True


class PatternEngine:
    def __init__(self):
        self.rules: List[PatternRule] = []

    def register_rule(self, rule: PatternRule):
        self.rules.append(rule)

    def analyze(self, root: Any) -> List[Dict[str, Any]]:
        """
        Walk `root` (Program or node) and return a list of suggestions:
          { "rule": rule.name, "node": node, "location": parent_info, "description": rule.description }
        """
        suggestions: List[Dict[str, Any]] = []
        for parent, attr_name, node in self._walk_with_parents(root):
            for rule in self.rules:
                if rule.matches(node):
                    suggestions.append({
                        "rule": rule.name,
                        "node": node,
                        "parent": parent,
                        "parent_attr": attr_name,
                        "description": rule.description,
                    })
        return suggestions

    def apply_transforms(self, root: Any) -> Tuple[Any, List[Dict[str, Any]]]:
        """
        Apply registered rules that have actions. Replaces nodes when action returns a node.
        Returns (root, list_of_applied_actions)
        """
        applied: List[Dict[str, Any]] = []
        # Collect matches first to avoid mutating while iterating in unpredictable ways
        matches = []
        for parent, attr_name, node in self._walk_with_parents(root):
            for rule in self.rules:
                if rule.action and rule.matches(node):
                    matches.append((parent, attr_name, node, rule))
        # Apply replacements
        for parent, attr_name, node, rule in matches:
            try:
                replacement = rule.action(node)
            except Exception as ex:
                replacement = None
            if replacement is None:
                applied.append({"rule": rule.name, "node": node, "replaced": False})
                continue
            # perform replacement on parent
            if parent is None:
                # Replacing the root node
                root = replacement
            else:
                self._assign_to_parent(parent, attr_name, replacement)
            applied.append({"rule": rule.name, "node": node, "replaced": True, "replacement": replacement})
        return root, applied

    # --- Internal helpers ---

    def _walk_with_parents(self, node: Any):
        """
        Yields tuples (parent, attr_name, child_node) for nodes found in the AST.
        For top-level nodes in Program.body, parent is the Program instance and attr_name is 'body'.
        """
        if node is None:
            return
        # If this is a Program with a `body` attribute (list)
        if hasattr(node, "body") and isinstance(node.body, list):
            for idx, child in enumerate(node.body):
                yield (node, ("body", idx), child)
                # Recurse into child
                yield from self._walk_with_parents(child)
            return
        # If node has attributes that are lists or nested nodes, attempt to traverse common shapes
        for name, value in inspect.getmembers(node, lambda v: not(inspect.isroutine(v))):
            if name.startswith("_"):
                continue
            if name in ("body",):  # already handled above
                continue
            if isinstance(value, list):
                for idx, item in enumerate(value):
                    if self._is_ast_node(item):
                        yield (node, (name, idx), item)
                        yield from self._walk_with_parents(item)
            elif self._is_ast_node(value):
                yield (node, (name, None), value)
                yield from self._walk_with_parents(value)

    @staticmethod
    def _is_ast_node(obj: Any) -> bool:
        return hasattr(obj, "__class__") and obj.__class__.__module__ != 'builtins'

    @staticmethod
    def _assign_to_parent(parent: Any, attr_info: Tuple[str, Optional[int]], replacement: Any):
        """
        attr_info is (attr_name, index) where index may be None for single attributes.
        """
        attr_name, idx = attr_info
        if not hasattr(parent, attr_name):
            return
        cur = getattr(parent, attr_name)
        if idx is None:
            setattr(parent, attr_name, replacement)
        else:
            if isinstance(cur, list):
                cur[idx] = replacement
            else:
                setattr(parent, attr_name, replacement)


# -------------------------
# Built-in rules (examples)
# -------------------------

def _is_empty_list(x):
    return isinstance(x, list) and len(x) == 0

# Rule: Remove empty capsules (suggest removal; action returns None -> suggestion only)
remove_empty_capsule_rule = PatternRule(
    name="RemoveEmptyCapsule",
    pattern={
        "__type__": "Capsule",
        "attrs": {
            "body": _is_empty_list
        }
    },
    action=lambda node: None,
    description="Capsule has an empty body; consider removing or consolidating it."
)

# Rule: Convert single-statement capsule into inlined MainBlock (example action)
def _inline_single_statement_capsule_action(node):
    """
    If Capsule contains exactly one statement and that statement is simple,
    return that statement to replace the Capsule in the parent's body.
    """
    if not hasattr(node, "body") or not isinstance(node.body, list):
        return None
    if len(node.body) != 1:
        return None
    return node.body[0]  # perform inlining by replacing the Capsule with its single child

inline_single_stmt_capsule_rule = PatternRule(
    name="InlineSingleStatementCapsule",
    pattern={
        "__type__": "Capsule",
        "attrs": {
            "body": lambda v: isinstance(v, list) and len(v) == 1
        }
    },
    action=_inline_single_statement_capsule_action,
    description="Inline a capsule that contains a single statement into its parent to reduce nesting."
)

# Rule registry convenience
def default_engine_with_examples() -> PatternEngine:
    engine = PatternEngine()
    engine.register_rule(remove_empty_capsule_rule)
    engine.register_rule(inline_single_stmt_capsule_rule)
    return engine


# -------------------------
# Minimal self-test / example
# -------------------------
if __name__ == "__main__":
    # Lightweight smoke test demonstrating API
    from ast import Program, Capsule

    engine = default_engine_with_examples()
    # Program with an empty capsule and a capsule with one simple 'stmt' object
    p = Program([
        Capsule("Empty"),
        Capsule("Single"),
    ])
    # give the second capsule a single dummy statement (use a simple object)
    p.body[1].body.append("Print: hello")  # the AST can contain primitive statements for this example

    print("Analysis suggestions:")
    for s in engine.analyze(p):
        print("-", s["rule"], "on", getattr(s["node"], "name", type(s["node"]).__name__), ":", s["description"])

    root_after, applied = engine.apply_transforms(p)
    print("\nApplied actions:")
    for a in applied:
        print("-", a["rule"], "replaced?" , a["replaced"])
    print("\nFinal program body:")
    for item in root_after.body:
        print("-", item if not hasattr(item, "name") else f"Capsule({item.name})")
        # Program with an empty capsule and a capsule with one simple 'stmt' object
        # give the second capsule a single dummy statement (use a simple object)
        # p.body[1].body.append("Print: hello")  # the AST can contain primitive statements for this example
        # print("Analysis suggestions:")
        if hasattr(item, "body"):
            for stmt in item.body:
                print("   -", stmt)
                
# dodecagram.py
"""
Dodecagram (base-12) encoder/decoder utilities.

Provides:
- to_base12(n, min_width=0) -> str
- from_base12(s) -> int
- is_valid_dodecagram(s) -> bool
- bytes_to_base12(b) -> str
- base12_to_bytes(s, length=None) -> bytes

Digits mapping: 0-9, a=10, b=11
"""

from typing import Optional

DIGITS = "0123456789ab"
_DIGIT_MAP = {ch: i for i, ch in enumerate(DIGITS)}
__all__ = [
    "DIGITS",
    "to_base12",
    "from_base12",
    "is_valid_dodecagram",
    "bytes_to_base12",
    "base12_to_bytes",
]


def to_base12(n: int, min_width: int = 0) -> str:
    """
    Convert integer `n` to base-12 string using digits 0-9,a,b.
    Supports negative integers. Pads with leading zeros to `min_width`.
    """
    if not isinstance(n, int):
        raise TypeError("to_base12 expects an int")
    if n == 0:
        return "0".rjust(max(0, min_width), "0")
    neg = n < 0
    n_abs = -n if neg else n
    digits = []
    while n_abs:
        digits.append(DIGITS[n_abs % 12])
        n_abs //= 12
    s = "".join(reversed(digits))
    if min_width and len(s) < min_width:
        s = s.rjust(min_width, "0")
    return ("-" + s) if neg else s


def from_base12(s: str) -> int:
    """
    Parse a base-12 string `s` (digits 0-9,a,b). Underscores and spaces allowed and ignored.
    Accepts an optional leading + or - sign.
    Raises ValueError for invalid characters.
    """
    if not isinstance(s, str):
        raise TypeError("from_base12 expects a str")
    s = s.strip()
    if s == "":
        raise ValueError("empty string")
    sign = 1
    if s[0] in ("+", "-"):
        if s[0] == "-":
            sign = -1
        s = s[1:].lstrip()
    # ignore separators
    s = s.replace("_", "").replace(" ", "")
    if s == "":
        raise ValueError("no digits after sign/separators")
    value = 0
    for ch in s:
        ch_lower = ch.lower()
        if ch_lower not in _DIGIT_MAP:
            raise ValueError(f"invalid base-12 digit: {ch}")
        value = value * 12 + _DIGIT_MAP[ch_lower]
    return sign * value


def is_valid_dodecagram(s: str) -> bool:
    """Return True if `s` is a valid base-12 representation (ignoring separators)."""
    try:
        from_base12(s)
        return True
    except Exception:
        return False


def bytes_to_base12(b: bytes) -> str:
    """
    Encode arbitrary bytes to a base-12 integer representation.
    This treats the bytes as a big-endian unsigned integer and returns its base-12 string.
    Empty bytes produce "0".
    """
    if not isinstance(b, (bytes, bytearray)):
        raise TypeError("bytes_to_base12 expects bytes or bytearray")
    if len(b) == 0:
        return "0"
    n = int.from_bytes(b, byteorder="big", signed=False)
    return to_base12(n)


def base12_to_bytes(s: str, length: Optional[int] = None) -> bytes:
    """
    Decode a base-12 string `s` into bytes (big-endian).
    If `length` is provided, the result is padded (or validated) to that many bytes.
    If `length` is None, the minimal number of bytes to hold the integer is returned.
    """
    n = from_base12(s)
    if n < 0:
        raise ValueError("cannot convert negative base-12 value to bytes")
    if n == 0:
        result = b"" if length is None or length == 0 else (b"\x00" * length)
        return result
    min_len = (n.bit_length() + 7) // 8
    if length is None:
        length = min_len
    if length < min_len:
        raise ValueError(f"provided length {length} too small to hold value (needs {min_len})")
    return n.to_bytes(length, byteorder="big")


if __name__ == "__main__":
    # quick smoke tests
    tests = [0, 1, 11, 12, 144, 12345, -37]
    for n in tests:
        s = to_base12(n)
        back = from_base12(s)
        print(f"{n} -> {s} -> {back}")

    b = b"\x01\x02\x03"
    s = bytes_to_base12(b)
    b2 = base12_to_bytes(s)
    print("bytes", b, "->", s, "->", b2)

    # validation examples
    print(is_valid_dodecagram("1ab_0"))
    print(is_valid_dodecagram("xyz"))
    print(is_valid_dodecagram("-  9 8 7"))
    if len(sys.argv) < 2:
        print("Usage: python dodecagram.py <base12-string>")
        raise SystemExit(1)
    for arg in sys.argv[1:]:
        try:
            n = from_base12(arg)
            print(f"{arg} -> {n}")
        except Exception as ex:
            print(f"{arg} : error - {ex}")
            import sys
            sys.exit(1)
            import sys
            if len(sys.argv) < 2:
                print("Usage: python dodecagram.py <base12-string>")
                raise SystemExit(1)
            for arg in sys.argv[1:]:
                try:
                    n = from_base12(arg)
                    print(f"{arg} -> {n}")
                except Exception as ex:
                    print(f"{arg} : error - {ex}")
                    import sys
                    sys.exit(1)
                    
"""
nasm_embed.py

Extract inline NASM blocks from Trion source code between markers:
    --nasm-start [opts]
    --nasm-end

Returns a list of dicts with:
    - content: str (dedented NASM source)
    - start_line: int (1-based line number where block content starts)
    - end_line: int (1-based line number where block content ends)
    - meta: dict (parsed options from the start marker; supports key=value and flags)

Example start marker forms:
    --nasm-start
    --nasm-start name=init bits=64
    --nasm-start:label flag

This module is dependency-free and suitable for use in the Trion toolchain.
"""

from typing import Dict, List, Any
import re
import textwrap
import os
import argparse

_START_RE = re.compile(r'--\s*nasm-start(?::|\s+)?(.*)$')
_END_RE = re.compile(r'--\s*nasm-end\b')


def _parse_meta(meta_str: str) -> Dict[str, Any]:
    """
    Parse a metadata string from the start marker into a dict.
    Supports tokens like `key=value` or standalone `flag`.
    """
    meta: Dict[str, Any] = {}
    if not meta_str:
        return meta
    tokens = meta_str.strip().split()
    for tok in tokens:
        if '=' in tok:
            k, v = tok.split('=', 1)
            meta[k.strip()] = v.strip()
        else:
            meta[tok] = True
    return meta


def extract_nasm_blocks(code: str) -> List[Dict[str, Any]]:
    """
    Extract NASM blocks from the provided source `code`.

    Raises:
        ValueError: if a nested start is found or end marker is missing.

    Returns:
        List of dicts with keys: content, start_line, end_line, meta
    """
    blocks: List[Dict[str, Any]] = []
    inside = False
    current_lines: List[str] = []
    current_meta: Dict[str, Any] = {}
    content_start_line: int = 0

    # Normalize line endings and iterate with 1-based line numbers
    lines = code.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    for idx, line in enumerate(lines, start=1):
        # check for start marker
        m_start = _START_RE.search(line)
        if m_start:
            if inside:
                raise ValueError(f"Nested --nasm-start at line {idx}")
            inside = True
            current_lines = []
            current_meta = _parse_meta(m_start.group(1) or "")
            content_start_line = idx + 1  # content begins on following line
            continue

        # check for end marker
        if _END_RE.search(line):
            if not inside:
                # stray end; ignore it
                continue
            # finalize block
            inside = False
            content_end_line = idx - 1
            raw = "\n".join(current_lines)
            # dedent to remove common indentation
            content = textwrap.dedent(raw).rstrip("\n")
            blocks.append({
                "content": content,
                "start_line": content_start_line,
                "end_line": content_end_line,
                "meta": current_meta,
            })
            current_lines = []
            current_meta = {}
            content_start_line = 0
            continue

        # accumulate lines if inside
        if inside:
            current_lines.append(line)

    if inside:
        raise ValueError("Unclosed --nasm-start: missing --nasm-end before end of file")

    return blocks


def extract_nasm_blocks_from_file(path: str) -> List[Dict[str, Any]]:
    """
    Convenience helper: read a file and extract NASM blocks.
    """
    with open(path, "r", encoding="utf-8") as fh:
        code = fh.read()
    return extract_nasm_blocks(code)


if __name__ == "__main__":
    # CLI: print summaries, optionally dump contents or write blocks to files
    parser = argparse.ArgumentParser(description="Extract inline NASM blocks from a Trion source file.")
    parser.add_argument("path", help="Trion source file (.trn)")
    parser.add_argument("--dump", action="store_true", help="Print full content of each extracted NASM block")
    parser.add_argument("--write-blocks", action="store_true", help="Write each NASM block to separate .nasm files")
    parser.add_argument("--out-dir", default=".", help="Directory to write extracted blocks when --write-blocks is used")
    args = parser.parse_args()

    if not os.path.exists(args.path):
        print("File not found:", args.path)
        raise SystemExit(2)

    try:
        blocks = extract_nasm_blocks_from_file(args.path)
    except Exception as ex:
        print("Error extracting NASM blocks:", ex)
        raise

    base_name = os.path.splitext(os.path.basename(args.path))[0]
    for i, b in enumerate(blocks, start=1):
        meta = " ".join(f"{k}={v}" if v is not True else k for k, v in b["meta"].items())
        print(f"Block {i}: lines {b['start_line']}-{b['end_line']} meta=({meta}) size={len(b['content'])} bytes")
        if args.dump:
            print("---- BEGIN BLOCK ----")
            print(b["content"])
            print("----  END BLOCK  ----")
        if args.write_blocks:
            os.makedirs(args.out_dir, exist_ok=True)
            # prefer meta name if provided, else numbered file
            name_hint = b["meta"].get("name") if isinstance(b["meta"].get("name"), str) else None
            out_filename = f"{base_name}.{name_hint or 'nasm'}.{i}.asm"
            out_path = os.path.join(args.out_dir, out_filename)
            with open(out_path, "w", encoding="utf-8") as out_f:
                out_f.write(b["content"])
            print(f"Wrote block {i} to {out_path}")
"""
html_embed.py

Extract inline HTML blocks from Trion source code.

Supports:
 - Comment-marked blocks using Trion comments:
     --html-start [key=value ...]
     ...
     --html-end
 - Explicit <html ...>...</html> tag blocks (supports attributes on the opening tag)

Returns a list of dicts:
    {
      "raw": str,           # full block including markers or tags
      "content": str,       # inner HTML (dedented)
      "start_line": int,    # 1-based line where content starts
      "end_line": int,      # 1-based line where content ends
      "meta": dict,         # parsed metadata from marker OR tag attributes
      "type": "marker"|"tag"#
    }

This module is dependency-free and tolerant to mixed usages.
"""

from typing import List, Dict, Any, Tuple
import re
import textwrap
import os

_MARKER_START_RE = re.compile(r'--\s*html-start(?::|\s+)?(.*)$')
_MARKER_END_RE = re.compile(r'--\s*html-end\b')
_TAG_START_RE = re.compile(r'<html\b([^>]*)>', flags=re.IGNORECASE)
_TAG_END_RE = re.compile(r'</html>', flags=re.IGNORECASE)
_ATTR_RE = re.compile(r'([A-Za-z_:][-A-Za-z0-9_:.]*)\s*=\s*"(.*?)"|([A-Za-z_:][-A-Za-z0-9_:.]*)\s*=\s*([^\s">]+)')

def _parse_meta(meta_str: str) -> Dict[str, Any]:
    """
    Parse a simple meta token string like: 'name=foo mode=compact flag'
    into a dict. Flags get value True.
    """
    meta: Dict[str, Any] = {}
    if not meta_str:
        return meta
    tokens = meta_str.strip().split()
    for tok in tokens:
        if '=' in tok:
            k, v = tok.split('=', 1)
            meta[k.strip()] = v.strip().strip('"')
        else:
            meta[tok] = True
    return meta

def _parse_tag_attrs(attr_text: str) -> Dict[str, Any]:
    attrs: Dict[str, Any] = {}
    if not attr_text:
        return attrs
    for m in _ATTR_RE.finditer(attr_text):
        if m.group(1):
            attrs[m.group(1)] = m.group(2)
        elif m.group(3):
            attrs[m.group(3)] = m.group(4)
    return attrs

def extract_html_blocks(code: str) -> List[Dict[str, Any]]:
    """
    Extract HTML blocks from `code`. Supports both marker-style and <html> tags.
    Raises ValueError for unclosed marker-style blocks.
    """
    blocks: List[Dict[str, Any]] = []

    # Normalize line endings and iterate with 1-based line numbers
    lines = code.replace('\r\n', '\n').replace('\r', '\n').split('\n')

    # First pass: marker-style blocks (line-oriented)
    inside = False
    current_lines: List[str] = []
    current_meta: Dict[str, Any] = {}
    content_start_line = 0

    for idx, line in enumerate(lines, start=1):
        m_start = _MARKER_START_RE.search(line)
        if m_start:
            if inside:
                raise ValueError(f"Nested --html-start at line {idx}")
            inside = True
            current_lines = []
            current_meta = _parse_meta(m_start.group(1) or "")
            content_start_line = idx + 1
            continue

        if _MARKER_END_RE.search(line):
            if not inside:
                # stray end marker; ignore
                continue
            inside = False
            content_end_line = idx - 1
            raw = "\n".join(lines[content_start_line - 1: content_end_line])
            content = textwrap.dedent("\n".join(current_lines)).rstrip("\n")
            blocks.append({
                "raw": "\n".join(lines[content_start_line - 2: idx]) if content_start_line >= 2 else ("\n".join(lines[:idx])),
                "content": content,
                "start_line": content_start_line,
                "end_line": content_end_line,
                "meta": current_meta,
                "type": "marker",
            })
            current_lines = []
            current_meta = {}
            content_start_line = 0
            continue

        if inside:
            current_lines.append(line)

    if inside:
        raise ValueError("Unclosed --html-start: missing --html-end before end of file")

    # Second pass: tag-style blocks. We avoid duplicating blocks already captured by markers.
    # We'll scan the full text and track used regions (by line ranges) to skip overlaps.
    used_ranges: List[Tuple[int, int]] = [(b["start_line"], b["end_line"]) for b in blocks]

    text = "\n".join(lines)
    pos = 0
    while True:
        m_tag = _TAG_START_RE.search(text, pos)
        if not m_tag:
            break
        tag_start = m_tag.start()
        attr_text = m_tag.group(1) or ""
        tag_attrs = _parse_tag_attrs(attr_text)
        # find corresponding end tag
        m_end = _TAG_END_RE.search(text, m_tag.end())
        if not m_end:
            # no closing tag; treat as error and stop scanning further tags
            break
        tag_end = m_end.end()
        # compute line numbers
        start_line = text.count("\n", 0, m_tag.end()) + 1  # line where content after '>' may begin
        # position after the '>'
        content_begin_pos = m_tag.end()
        content_end_pos = m_end.start()
        end_line = text.count("\n", 0, content_end_pos) + 1

        # Determine if this range overlaps existing marker-based blocks; if so, skip to avoid duplicates
        overlap = False
        for rstart, rend in used_ranges:
            if not (end_line < rstart or start_line > rend):
                overlap = True
                break
        if not overlap:
            raw_block = text[m_tag.start(): tag_end]
            inner = text[content_begin_pos:content_end_pos]
            content = textwrap.dedent(inner).rstrip("\n")
            blocks.append({
                "raw": raw_block,
                "content": content,
                "start_line": start_line,
                "end_line": end_line,
                "meta": tag_attrs,
                "type": "tag",
            })
            used_ranges.append((start_line, end_line))
        pos = tag_end

    return blocks

def extract_html_blocks_from_file(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        code = f.read()
    return extract_html_blocks(code)

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python html_embed.py <file.trn>")
        raise SystemExit(2)
    path = sys.argv[1]
    if not os.path.exists(path):
        print("File not found:", path)
        raise SystemExit(2)
    for i, b in enumerate(extract_html_blocks_from_file(path), start=1):
        meta = " ".join(f'{k}="{v}"' if v is not True else k for k, v in b["meta"].items())
        print(f"Block {i}: type={b['type']} lines={b['start_line']}-{b['end_line']} meta=({meta}) size={len(b['content'])} chars")
        if b['content']:
            print(b['content'])
            print("-" * 40)

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

"""
TrionPatternAI.py
Pattern matching and deduction helpers for the Trion compiler.

Provides:
- PatternRule: declarative pattern + optional transformation action
- PatternEngine: register rules, analyze AST, produce suggestions, apply safe transforms

This module is intentionally small, dependency-free and designed to work with the
simple AST classes in `ast.py` (Program, Capsule, MainBlock). Patterns are
simple dictionaries describing node types and attribute constraints.

Example usage:
    from ast import Program, Capsule
    engine = PatternEngine()
    engine.register_rule(remove_empty_capsule_rule)
    program = Program([ Capsule("Empty") ])
    suggestions = engine.analyze(program)
    engine.apply_transforms(program)
"""

from typing import Any, Callable, Dict, List, Optional, Tuple
import inspect

# Types
Pattern = Dict[str, Any]
Action = Callable[[Any], Optional[Any]]  # action(node) -> replacement or None


class PatternRule:
    def __init__(self, name: str, pattern: Pattern, action: Optional[Action] = None, description: str = ""):
        """
        pattern: {
            "__type__": "Capsule",         # optional: class name to match
            "attrs": { "name": "Foo" },    # optional: attribute name -> expected or callable
        }
        action: function that receives the matched node and returns:
                - None to indicate no structural replacement (only suggestion)
                - a new node to replace the matched node
        """
        self.name = name
        self.pattern = pattern
        self.action = action
        self.description = description

    def matches(self, node: Any) -> bool:
        # Match type
        t = self.pattern.get("__type__")
        if t:
            if type(node).__name__ != t:
                return False
        # Match attributes
        attrs = self.pattern.get("attrs", {})
        for k, expected in attrs.items():
            if not hasattr(node, k):
                return False
            val = getattr(node, k)
            if callable(expected):
                try:
                    if not expected(val):
                        return False
                except Exception:
                    return False
            else:
                if val != expected:
                    return False
        return True


class PatternEngine:
    def __init__(self):
        self.rules: List[PatternRule] = []

    def register_rule(self, rule: PatternRule):
        self.rules.append(rule)

    def analyze(self, root: Any) -> List[Dict[str, Any]]:
        """
        Walk `root` (Program or node) and return a list of suggestions:
          { "rule": rule.name, "node": node, "location": parent_info, "description": rule.description }
        """
        suggestions: List[Dict[str, Any]] = []
        for parent, attr_name, node in self._walk_with_parents(root):
            for rule in self.rules:
                if rule.matches(node):
                    suggestions.append({
                        "rule": rule.name,
                        "node": node,
                        "parent": parent,
                        "parent_attr": attr_name,
                        "description": rule.description,
                    })
        return suggestions

    def apply_transforms(self, root: Any) -> Tuple[Any, List[Dict[str, Any]]]:
        """
        Apply registered rules that have actions. Replaces nodes when action returns a node.
        Returns (root, list_of_applied_actions)
        """
        applied: List[Dict[str, Any]] = []
        # Collect matches first to avoid mutating while iterating in unpredictable ways
        matches = []
        for parent, attr_name, node in self._walk_with_parents(root):
            for rule in self.rules:
                if rule.action and rule.matches(node):
                    matches.append((parent, attr_name, node, rule))
        # Apply replacements
        for parent, attr_name, node, rule in matches:
            try:
                replacement = rule.action(node)
            except Exception as ex:
                replacement = None
            if replacement is None:
                applied.append({"rule": rule.name, "node": node, "replaced": False})
                continue
            # perform replacement on parent
            if parent is None:
                # Replacing the root node
                root = replacement
            else:
                self._assign_to_parent(parent, attr_name, replacement)
            applied.append({"rule": rule.name, "node": node, "replaced": True, "replacement": replacement})
        return root, applied

    # --- Internal helpers ---

    def _walk_with_parents(self, node: Any):
        """
        Yields tuples (parent, attr_name, child_node) for nodes found in the AST.
        For top-level nodes in Program.body, parent is the Program instance and attr_name is 'body'.
        """
        if node is None:
            return
        # If this is a Program with a `body` attribute (list)
        if hasattr(node, "body") and isinstance(node.body, list):
            for idx, child in enumerate(node.body):
                yield (node, ("body", idx), child)
                # Recurse into child
                yield from self._walk_with_parents(child)
            return
        # If node has attributes that are lists or nested nodes, attempt to traverse common shapes
        for name, value in inspect.getmembers(node, lambda v: not(inspect.isroutine(v))):
            if name.startswith("_"):
                continue
            if name in ("body",):  # already handled above
                continue
            if isinstance(value, list):
                for idx, item in enumerate(value):
                    if self._is_ast_node(item):
                        yield (node, (name, idx), item)
                        yield from self._walk_with_parents(item)
            elif self._is_ast_node(value):
                yield (node, (name, None), value)
                yield from self._walk_with_parents(value)

    @staticmethod
    def _is_ast_node(obj: Any) -> bool:
        return hasattr(obj, "__class__") and obj.__class__.__module__ != 'builtins'

    @staticmethod
    def _assign_to_parent(parent: Any, attr_info: Tuple[str, Optional[int]], replacement: Any):
        """
        attr_info is (attr_name, index) where index may be None for single attributes.
        """
        attr_name, idx = attr_info
        if not hasattr(parent, attr_name):
            return
        cur = getattr(parent, attr_name)
        if idx is None:
            setattr(parent, attr_name, replacement)
        else:
            if isinstance(cur, list):
                cur[idx] = replacement
            else:
                setattr(parent, attr_name, replacement)


# -------------------------
# Built-in rules (examples)
# -------------------------

def _is_empty_list(x):
    return isinstance(x, list) and len(x) == 0

# Rule: Remove empty capsules (suggest removal; action returns None -> suggestion only)
remove_empty_capsule_rule = PatternRule(
    name="RemoveEmptyCapsule",
    pattern={
        "__type__": "Capsule",
        "attrs": {
            "body": _is_empty_list
        }
    },
    action=lambda node: None,
    description="Capsule has an empty body; consider removing or consolidating it."
)

# Rule: Convert single-statement capsule into inlined MainBlock (example action)
def _inline_single_statement_capsule_action(node):
    """
    If Capsule contains exactly one statement and that statement is simple,
    return that statement to replace the Capsule in the parent's body.
    """
    if not hasattr(node, "body") or not isinstance(node.body, list):
        return None
    if len(node.body) != 1:
        return None
    return node.body[0]  # perform inlining by replacing the Capsule with its single child

inline_single_stmt_capsule_rule = PatternRule(
    name="InlineSingleStatementCapsule",
    pattern={
        "__type__": "Capsule",
        "attrs": {
            "body": lambda v: isinstance(v, list) and len(v) == 1
        }
    },
    action=_inline_single_statement_capsule_action,
    description="Inline a capsule that contains a single statement into its parent to reduce nesting."
)

# Rule registry convenience
def default_engine_with_examples() -> PatternEngine:
    engine = PatternEngine()
    engine.register_rule(remove_empty_capsule_rule)
    engine.register_rule(inline_single_stmt_capsule_rule)
    return engine


# -------------------------
# Minimal self-test / example
# -------------------------
if __name__ == "__main__":
    # Lightweight smoke test demonstrating API
    from ast import Program, Capsule

    engine = default_engine_with_examples()
    # Program with an empty capsule and a capsule with one simple 'stmt' object
    p = Program([
        Capsule("Empty"),
        Capsule("Single"),
    ])
    # give the second capsule a single dummy statement (use a simple object)
    p.body[1].body.append("Print: hello")  # the AST can contain primitive statements for this example

    print("Analysis suggestions:")
    for s in engine.analyze(p):
        print("-", s["rule"], "on", getattr(s["node"], "name", type(s["node"]).__name__), ":", s["description"])

    root_after, applied = engine.apply_transforms(p)
    print("\nApplied actions:")
    for a in applied:
        print("-", a["rule"], "replaced?" , a["replaced"])
    print("\nFinal program body:")
    for item in root_after.body:
        print("-", item if not hasattr(item, "name") else f"Capsule({item.name})")
        # Program with an empty capsule and a capsule with one simple 'stmt' object
        # give the second capsule a single dummy statement (use a simple object)
        # p.body[1].body.append("Print: hello")  # the AST can contain primitive statements for this example
        # print("Analysis suggestions:")
        if hasattr(item, "body"):
            for stmt in item.body:
                print("   -", stmt)
                

