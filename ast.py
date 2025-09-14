# ast.py

class Program:
    def __init__(self, body):
        self.body = body

class MainBlock:
    def __init__(self):
        self.type = "Main"

class Capsule:
    def __init__(self, name):
        self.name = name
        self.body = []

    def add(self, stmt):
        self.body.append(stmt)
