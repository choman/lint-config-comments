"""Shared helpers: comment alignment, description blocks, config discovery."""

import json
import re
import sys
from collections.abc import Callable
from pathlib import Path

import tomlkit

ITEM_RE = re.compile(r'^(\s+"[^"]*",)\s*(#.*)$')
KEY_RE = re.compile(r'^("(?:[^"\\]|\\.)*"|[A-Za-z0-9_-]+)\s*=\s*\[')

# (section, key) -> selectors used in that list
Items = dict[tuple[str, str], set]
# selector -> (selector, name, description)
RowFn = Callable[[str], tuple[str, str, str]]


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
        if skipping and line.startswith("#   "):
            continue
        skipping = False
        out.append(line)
    return "\n".join(out)


def add_rule_blocks(text: str, items: Items, row: RowFn, marker: str) -> str:
    """Insert a description block above each rule list."""
    out, section = [], ""
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped.strip("[]").strip()
        elif m := KEY_RE.match(line):
            key = json.loads(m.group(1)) if m.group(1).startswith('"') else m.group(1)
            sels = items.get((section, key))
            if sels:
                rows = [row(s) for s in sorted(sels, key=natural_key)]
                w1 = max(len(r[0]) for r in rows)
                w2 = max(len(r[1]) for r in rows)
                out.append(marker)
                out.extend(f"#   {a.ljust(w1)}  {b.ljust(w2)}  {shorten(c)}".rstrip() for a, b, c in rows)
        out.append(line)
    return "\n".join(out)


def find_config(names: list[str], accept: Callable[[Path], bool] = lambda p: True) -> Path | None:
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


def resolve_configs(paths: list[Path], names: list[str], accept=lambda p: True) -> list[Path]:
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
