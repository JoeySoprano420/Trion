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
                
