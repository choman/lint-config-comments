"""Shared helpers: comment alignment, description blocks, config discovery."""

import json
import re
import sys
from collections.abc import Callable
from pathlib import Path

import tomlkit

ITEM_RE = re.compile(r'^(\s+"[^"]*",)\s*(#.*)$')
PART = r'(?:"(?:[^"\\]|\\.)*"|\'[^\']*\'|[A-Za-z0-9_-]+)'
PATH = rf"{PART}(?:\s*\.\s*{PART})*"
KEY_RE = re.compile(rf"^({PATH})\s*=\s*\[")
HEADER_RE = re.compile(rf"^\[\s*({PATH})\s*\]\s*(#.*)?$")
INDENT_RE = re.compile(r'^( +)"[^"]*",?\s*(#.*)?$')

# full dotted path of a rule list, e.g. ("tool", "ruff", "lint", "select") -> selectors
Items = dict[tuple[str, ...], set]
# selector -> (selector, name, description)
RowFn = Callable[[str], tuple[str, str, str]]


def split_path(path: str) -> tuple[str, ...]:
    """'tool.ruff."per-file-ignores"' -> ('tool', 'ruff', 'per-file-ignores')"""
    parts = re.findall(PART, path)
    return tuple(json.loads(p) if p.startswith('"') else p.strip("'") for p in parts)


def detect_indent(text: str, default: int = 4) -> str:
    """Reuse the indent of existing multi-line arrays (e.g. 2 for pyproject-fmt)."""
    for line in text.split("\n"):
        if m := INDENT_RE.match(line):
            return m.group(1)
    return " " * default


def natural_key(code: str):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", code)]


def shorten(text: str, width: int = 72) -> str:
    return text if len(text) <= width else text[: width - 3].rstrip() + "..."


def align_comments(text: str) -> str:
    """Line up trailing comments within each run of consecutive array-item lines."""
    out, block = [], []

    def flush():
        if block:
            width = max(len(m.group(1)) for m in block)
            out.extend(f"{m.group(1).ljust(width)} {m.group(2)}" for m in block)
            block.clear()

    for line in text.split("\n"):
        if m := ITEM_RE.match(line):
            block.append(m)
        else:
            flush()
            out.append(line)
    flush()
    return "\n".join(out)


def strip_rule_blocks(text: str, markers: set[str]) -> str:
    """Remove description blocks written by a previous run."""
    out, skipping = [], False
    for line in text.split("\n"):
        if line in markers:
            skipping = True
            continue
        if skipping and line.lstrip().startswith("#"):
            continue
        skipping = False
        out.append(line)
    return "\n".join(out)


GENERATED_RE = re.compile(r"^#\s+(\S+)\s{2,}\S")


def remove_orphans(text: str, is_selector: Callable[[str], bool]) -> str:
    """Drop stray generated rows (left by older versions) from comments directly above a rule list.

    Only lines shaped like `# <known rule>  <name>...` in the comment run that
    immediately precedes a `key = [` line are removed; other comments stay.
    """
    lines = text.split("\n")
    drop = set()
    for i, line in enumerate(lines):
        if not KEY_RE.match(line):
            continue
        j = i - 1
        while j >= 0 and lines[j].lstrip().startswith("#"):
            m = GENERATED_RE.match(lines[j].strip())
            if m and is_selector(m.group(1)):
                drop.add(j)
            j -= 1
    return "\n".join(l for k, l in enumerate(lines) if k not in drop)


def sort_key(mode: str, value: str, code: str | None):
    """id: natural order by rule ID; value / ivalue: plain string order, as
    toml-sort --sort-inline-arrays does (ivalue = with --ignore-case)."""
    if mode == "value":
        return (value,)
    if mode == "ivalue":
        return (value.lower(),)
    return (code is None, natural_key(code or value))


ARRAY_ITEM_RE = re.compile(r'^(\s+)("(?:[^"\\]|\\.)*")(,?)\s*(#.*)?$')


def format_arrays(text: str, style) -> str:
    """Normalize multi-line arrays that carry comments: commas and comment spacing.

    With style.align, trailing comments line up; otherwise they get exactly
    style.comment_spaces spaces (what toml-sort writes). The last item keeps its
    comma only if style.trailing_comma.
    """
    lines = text.split("\n")
    out, i = [], 0
    while i < len(lines):
        run = []
        while i < len(lines) and (m := ARRAY_ITEM_RE.match(lines[i])):
            run.append(m)
            i += 1
        closes = i < len(lines) and lines[i].strip() == "]"
        if not run:
            out.append(lines[i])
            i += 1
            continue
        if not closes or not any(m.group(4) for m in run):
            out.extend(m.group(0) for m in run)  # not ours; leave untouched
            continue
        cells = []
        for n, m in enumerate(run):
            last = n == len(run) - 1
            comma = "," if (not last or style.trailing_comma) else ""
            cells.append((m.group(1) + m.group(2) + comma, m.group(4)))
        width = max(len(c) for c, cm in cells if cm)
        for cell, comment in cells:
            if not comment:
                out.append(cell)
            elif style.align:
                out.append(f"{cell.ljust(width)} {comment}")
            else:
                out.append(f"{cell}{' ' * style.comment_spaces}{comment}")
    return "\n".join(out)


def add_rule_blocks(
    text: str, items: Items, row: RowFn, marker: str, prefix: str = "#   "
) -> str:
    """Insert a description block above each rule list.

    Rows are indented under the marker (prefix "#   "), except in files
    toml-sort formats: it rewrites every comment to "# text".
    """
    out, section = [], ()
    for line in text.split("\n"):
        if m := HEADER_RE.match(line.strip()):
            section = split_path(m.group(1))
        elif m := KEY_RE.match(line):
            sels = items.get(section + split_path(m.group(1)))
            if sels:
                rows = [row(s) for s in sorted(sels, key=natural_key)]
                w1 = max(len(r[0]) for r in rows)
                w2 = max(len(r[1]) for r in rows)
                out.append(marker)
                out.extend(
                    f"{prefix}{a.ljust(w1)}  {b.ljust(w2)}  {shorten(c)}".rstrip()
                    for a, b, c in rows
                )
        out.append(line)
    return "\n".join(out)


def find_config(
    names: list[str], accept: Callable[[Path], bool] = lambda p: True
) -> Path | None:
    """Walk up from cwd to the git root; return the first matching config."""
    start = Path.cwd().resolve()
    for d in [start, *start.parents]:
        for name in names:
            p = d / name
            if p.is_file() and accept(p):
                return p
        if (d / ".git").exists():
            break
    return None


def has_table(path: Path, *keys: str) -> bool:
    """True if the TOML file has the nested table, e.g. has_table(p, "tool", "ruff")."""
    node = tomlkit.parse(path.read_text())
    for k in keys:
        if k not in node:
            return False
        node = node[k]
    return True


def resolve_configs(
    paths: list[Path], names: list[str], accept=lambda p: True
) -> list[Path]:
    """Use the given paths (from pre-commit) or discover one."""
    if paths:
        return [p for p in paths if p.is_file() and accept(p)]
    found = find_config(names, accept)
    if not found:
        sys.exit(f"error: no config found ({', '.join(names)})")
    return [found]


def write_result(config: Path, original: str, out: str, dry_run: bool) -> bool:
    """Print or write; return True if the file changed."""
    if dry_run:
        sys.stdout.write(out)
        return False
    if out != original:
        config.write_text(out)
        print(f"updated {config}", file=sys.stderr)
        return True
    return False
