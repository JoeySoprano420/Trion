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

