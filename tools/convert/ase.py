"""3ds Max ASCII Export (.ase) parser.

Produces a tree of Node(key, values, children). Values are the raw tokens after
the key (quoted strings unquoted); children is a list for "{ ... }" blocks.
MESH_FACE / MESH_TFACE lines keep their tokens; helpers below decode them.
"""

import re

TOKEN = re.compile(r'"[^"]*"|\S+')


class Node:
    __slots__ = ("key", "values", "children")

    def __init__(self, key, values, children=None):
        self.key = key
        self.values = values
        self.children = children

    def find(self, key):
        for c in self.children or ():
            if c.key == key:
                return c
        return None

    def find_all(self, key):
        return [c for c in (self.children or ()) if c.key == key]

    def value(self, key, default=None):
        n = self.find(key)
        return n.values if n is not None else default

    def first(self, key, default=None):
        v = self.value(key)
        return v[0] if v else default


def parse_text(text):
    root = Node("ROOT", [], [])
    stack = [root]
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line == "}":
            if len(stack) > 1:
                stack.pop()
            continue
        if not line.startswith("*"):
            continue
        toks = [t[1:-1] if t.startswith('"') else t for t in TOKEN.findall(line)]
        opens = toks and toks[-1] == "{"
        if opens:
            toks = toks[:-1]
        node = Node(toks[0][1:], toks[1:], [] if opens else None)
        stack[-1].children.append(node)
        if opens:
            stack.append(node)
    return root


def parse_file(path):
    with open(path, encoding="cp1252", errors="replace") as fh:
        return parse_text(fh.read())


def floats(values):
    return [float(v) for v in values]


def node_tm(obj):
    """4x3 world matrix rows from NODE_TM (row-vector convention: v' = v * M)."""
    tm = obj.find("NODE_TM")
    return [floats(tm.value(f"TM_ROW{i}")) for i in range(4)]


def mesh_face(values):
    """'0:' 'A:' '0' 'B:' '1' 'C:' '2' ... -> (0, 1, 2)."""
    out = {}
    for i, v in enumerate(values):
        if v in ("A:", "B:", "C:"):
            out[v[0]] = int(values[i + 1])
    return out["A"], out["B"], out["C"]
