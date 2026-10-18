"""Parser for MC2 FIT files, the typed INI format read by MCLib/Inifile.cpp.

    FITini
    [Block]
    st Name = "text"          // comment
    f[3] LODScales = 1.0, 0.5, 0.3,
    l[256] Table =
        9,9,9,...
    FITend

Types: l/ul/s/c/uc are integers, f is float, b is TRUE/FALSE (or 0/1), st is a
string. A bracketed count makes an array; its values may continue across lines.
Files are Windows-1252. Repeated names inside a block keep the last value, as
the game does on lookup.
"""

import re

INT_TYPES = {"l", "ul", "s", "c", "uc"}
NUMBER = re.compile(r"[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?")
STATEMENT = re.compile(r"^(l|ul|s|c|uc|f|b|st)(\[(\d+)\])?\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")


def strip_comment(line):
    """Drop a // comment unless it sits inside a quoted string."""
    in_str = False
    for i, ch in enumerate(line):
        if ch == '"':
            in_str = not in_str
        elif not in_str and line.startswith("//", i):
            return line[:i]
    return line


def _leading_number(raw):
    """atof/atol semantics: parse the leading number, ignore trailing junk ("60;", "1280.0f")."""
    m = NUMBER.match(raw)
    return float(m.group(0)) if m else 0.0


def _scalar(type_, raw):
    raw = raw.strip()
    if type_ == "st":
        if len(raw) >= 2 and raw[0] == '"' and raw[-1] == '"':
            return raw[1:-1]
        return raw.strip('"')
    if type_ == "b":
        up = raw.upper()
        if up in ("TRUE", "1", "T", "YES", "Y"):
            return True
        if up in ("FALSE", "0", "", "F", "NO", "N"):
            return False
        raise ValueError(f"bad boolean {raw!r}")
    if type_ == "f":
        return _leading_number(raw)
    if type_ in INT_TYPES:
        return int(_leading_number(raw))
    raise ValueError(f"unknown type {type_!r}")


def _split_values(text):
    """Split comma-separated values, keeping commas inside quotes."""
    out, cur, in_str = [], [], False
    for ch in text:
        if ch == '"':
            in_str = not in_str
            cur.append(ch)
        elif ch == "," and not in_str:
            out.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    out.append("".join(cur))
    return [v for v in (s.strip() for s in out) if v != ""]


def parse_text(text):
    blocks = {}
    block = None
    pending = None  # (type, count, name, collected value strings)

    def finish():
        nonlocal pending
        type_, count, name, parts = pending
        values = [_scalar(type_, v) for v in _split_values(",".join(parts))]
        if count is None:
            blocks[block][name] = values[0] if values else _scalar(type_, "")
        else:
            blocks[block][name] = values[:count]
        pending = None

    for raw_line in text.splitlines():
        line = strip_comment(raw_line).strip()
        if not line:
            continue
        if pending is not None:
            is_new = line.startswith("[") or STATEMENT.match(line) or line.startswith("FIT")
            if not is_new:
                pending[3].append(line)
                if len(_split_values(",".join(pending[3]))) >= pending[1]:
                    finish()
                continue
            finish()
        if line.startswith("FIT"):
            continue
        if line.startswith("[") and line.endswith("]"):
            block = line[1:-1].strip()
            blocks.setdefault(block, {})
            continue
        m = STATEMENT.match(line)
        if not m:
            continue  # stray text; the game's parser skips it too
        if block is None:
            block = ""
            blocks.setdefault(block, {})
        type_, _, count, name, value = m.groups()
        count = int(count) if count else None
        if count is None:
            blocks[block][name] = _scalar(type_, value)
        else:
            pending = (type_, count, name, [value] if value.strip() else [])
            if len(_split_values(value)) >= count:
                finish()
    if pending is not None:
        finish()
    return blocks


def parse_file(path):
    with open(path, encoding="cp1252", errors="replace") as fh:
        return parse_text(fh.read())
