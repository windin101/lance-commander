"""String table: resource.h symbols -> numbers, Script1.rc STRINGTABLE -> text.

The game looks strings up by number (cLoadString), e.g. component names are
32000 + masterID and mech descriptions use the chassis CSV's DescIndex.
"""

import re

DEFINE = re.compile(r"^#define\s+([A-Za-z_][A-Za-z0-9_]*)\s+(\d+)\s*$")
ENTRY = re.compile(r'^\s*([A-Za-z_][A-Za-z0-9_]*|\d+)\s*(".*")?\s*$')


def parse_defines(text):
    ids = {}
    for line in text.splitlines():
        m = DEFINE.match(line.strip())
        if m:
            ids[m.group(1)] = int(m.group(2))
    return ids


def _unquote(lit):
    """RC string literal: doubled quotes are a quote; \\n and \\t are escapes."""
    body = lit.strip()[1:-1].replace('""', '"')
    return body.replace("\\n", "\n").replace("\\t", "\t").replace("\\\\", "\\")


def parse_stringtables(text, ids):
    """Return {number: text}. An entry's literal may sit on the following line."""
    out = {}
    in_table = False
    pending_id = None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("STRINGTABLE"):
            in_table = True
            continue
        if not in_table:
            continue
        if s == "BEGIN" or not s:
            continue
        if s == "END":
            in_table = False
            pending_id = None
            continue
        if s.startswith('"') and pending_id is not None:
            out[pending_id] = _unquote(s)
            pending_id = None
            continue
        m = ENTRY.match(s)
        if not m:
            continue
        sym, lit = m.group(1), m.group(2)
        num = int(sym) if sym.isdigit() else ids.get(sym)
        if num is None:
            continue
        if lit:
            out[num] = _unquote(lit)
        else:
            pending_id = num
    return out


def load(rc_path, header_path):
    with open(header_path, encoding="cp1252", errors="replace") as fh:
        ids = parse_defines(fh.read())
    with open(rc_path, encoding="cp1252", errors="replace") as fh:
        return parse_stringtables(fh.read(), ids)
