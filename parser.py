# parser.py
from ast import *

class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def parse(self):
        nodes = []
        while self.pos < len(self.tokens):
            if self._match("KEYWORD", "Main"):
                nodes.append(self._parse_main())
            elif self._match("KEYWORD", "Capsule"):
                nodes.append(self._parse_capsule())
            else:
                self.pos += 1
        return Program(nodes)

    def _match(self, typ, val=None):
        if self.pos < len(self.tokens):
            t_type, t_val = self.tokens[self.pos]
            if t_type == typ and (val is None or t_val == val):
                return True
        return False

    def _parse_main(self):
        self.pos += 1
        return MainBlock()

    def _parse_capsule(self):
        self.pos += 1
        name = self.tokens[self.pos][1]
        self.pos += 1
        return Capsule(name)
