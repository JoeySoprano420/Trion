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

