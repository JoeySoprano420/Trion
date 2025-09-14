# lexer.py
import re

TOKEN_TYPES = [
    ("KEYWORD", r'\b(Main|Capsule|If|Then|Else|Elseif|While|For|EndCapsule|Print|Isolate|Try|Execute|Fail|True|False)\b'),
    ("IDENT", r'[a-zA-Z_][a-zA-Z0-9_]*'),
    ("NUMBER", r'\b\d+\b'),
    ("STRING", r'"[^"]*"'),
    ("OP", r'[+*/<>=,]'),
    ("COMMENT", r'--.*'),
    ("NEWLINE", r'\n'),
    ("SKIP", r'[ \t]+'),
    ("MISMATCH", r'.'),
]

def tokenize(code):
    tokens = []
    for line in code.splitlines():
        pos = 0
        while pos < len(line):
            for typ, pattern in TOKEN_TYPES:
                regex = re.compile(pattern)
                match = regex.match(line, pos)
                if match:
                    if typ != "SKIP" and typ != "COMMENT":
                        tokens.append((typ, match.group(0)))
                    pos = match.end()
                    break
    return tokens
