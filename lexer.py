-- lexer.py
import re

-- Define token types and patterns for Trion language
TOKEN_TYPES = [
    ("KEYWORD", r'\\b(Main|Capsule|If|Then|Else|Elseif|While|For|EndCapsule|Print|Isolate|Try|Execute|Fail|True|False)\\b'),
    ("IDENT", r'[a-zA-Z_][a-zA-Z0-9_]*'),
    ("NUMBER", r'\\b\\d+\\b'),
    ("STRING", r'"[^"]*"'),
    ("OP", r'[+*/<>=,]'),
    ("COMMENT", r'--.*'),
    ("NEWLINE", r'\\n'),
    ("SKIP", r'[ \\t]+'),
    ("MISMATCH", r'.'),
]

-- Tokenize input code into list of (type, value) tuples
def tokenize(code):
    tokens = []
    for line in code.splitlines():
        pos = 0
        while pos < len(line):
            for typ, pattern in TOKEN_TYPES:
                regex = re.compile(pattern)
                match = regex.match(line, pos)
                if match:
                    -- Ignore whitespace and comments
                    if typ != "SKIP" and typ != "COMMENT":
                        tokens.append((typ, match.group(0)))
                    pos = match.end()
                    break
    return tokens
