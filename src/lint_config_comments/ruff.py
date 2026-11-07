"""Annotate rule selectors in a ruff config with rule names and descriptions.

Ruff only accepts codes/prefixes (not rule names), so codes stay as the values.
"""

import argparse
import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import tomlkit

from .common import (
    Items, add_rule_blocks, align_comments, has_table, natural_key,
    resolve_configs, strip_rule_blocks, write_result,
)

DEFAULT_CMD = "ruff" if shutil.which("ruff") else "uvx ruff"
CONFIG_NAMES = [".ruff.toml", "ruff.toml", ".config/ruff.toml", "pyproject.toml"]
LIST_KEYS = {
    "select", "extend-select", "ignore", "extend-ignore",
    "fixable", "extend-fixable", "unfixable",
    "extend-safe-fixes", "extend-unsafe-fixes",
}
TABLE_KEYS = {"per-file-ignores", "extend-per-file-ignores"}
MARKER = "# ruff rules:"


def accept(path: Path) -> bool:
    return path.name != "pyproject.toml" or has_table(path, "tool", "ruff")


class RuffRules:
    def __init__(self, cmd: str = DEFAULT_CMD):
        base = shlex.split(cmd)
        rules = json.loads(subprocess.check_output([*base, "rule", "--all", "--output-format", "json"], text=True))
        linters = json.loads(subprocess.check_output([*base, "linter", "--output-format", "json"], text=True))

        self.rules = {r["code"]: (r["name"], r.get("summary", "")) for r in rules if r.get("code")}
        self.prefixes = {}
        for lint in linters:
            for cat in lint.get("categories") or []:
                self.prefixes[lint["prefix"] + cat["prefix"]] = f"{lint['name']} {cat['name']}"
            if lint["prefix"]:
                self.prefixes[lint["prefix"]] = lint["name"]

    def describe(self, sel: str) -> tuple[str, str] | None:
        """Return (label, description) for a code or prefix selector."""
        if sel in self.rules:
            return self.rules[sel]
        if sel == "ALL":
            return "ALL", "every rule"
        if sel in self.prefixes:
            return self.prefixes[sel], ""
        matches = [c for c in self.rules if c.startswith(sel)]
        if matches:
            owner = max((p for p in self.prefixes if sel.startswith(p)), key=len, default=None)
            return f"{self.prefixes.get(owner, 'prefix')} ({len(matches)} rules)", ""
        return None

    def row(self, sel: str) -> tuple[str, str, str]:
        return (sel, *self.describe(sel))


def rewrite(arr, rules: RuffRules, seen: set):
    new = tomlkit.array().multiline(True)
    for sel in sorted({str(s) for s in arr}, key=natural_key):
        info = rules.describe(sel)
        if info:
            seen.add(sel)
            new.add_line(sel, comment=info[0])
        else:
            print(f"warning: unknown selector {sel!r}, left as-is", file=sys.stderr)
            new.add_line(sel)
    return new


def lint_tables(doc, is_pyproject: bool):
    """Yield (dotted section, table) for every table that may hold lint settings."""
    root = doc.get("tool", {}).get("ruff") if is_pyproject else doc
    if root is None:
        return
    base = "tool.ruff" if is_pyproject else ""
    yield base, root  # legacy top-level settings
    if "lint" in root:
        yield f"{base}.lint".lstrip("."), root["lint"]


def process(config: Path, rules: RuffRules, describe: bool, dry_run: bool) -> bool:
    original = config.read_text()
    doc = tomlkit.parse(strip_rule_blocks(original, {MARKER}))
    items: Items = {}

    for section, table in lint_tables(doc, config.name == "pyproject.toml"):
        for key in LIST_KEYS & set(table):
            table[key] = rewrite(table[key], rules, items.setdefault((section, key), set()))
        for key in TABLE_KEYS & set(table):
            sub = f"{section}.{key}".lstrip(".")
            for pattern in list(table[key]):
                table[key][pattern] = rewrite(table[key][pattern], rules, items.setdefault((sub, pattern), set()))

    out = align_comments(tomlkit.dumps(doc))
    if describe:
        out = add_rule_blocks(out, items, rules.row, MARKER)
    return write_result(config, original, out, dry_run)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("configs", nargs="*", type=Path, help=f"config files (default: search for {', '.join(CONFIG_NAMES)})")
    ap.add_argument("--ruff", default=DEFAULT_CMD, help=f"ruff command (default: {DEFAULT_CMD!r})")
    ap.add_argument("-d", "--describe", action=argparse.BooleanOptionalAction, default=True,
                    help="comment block above each list describing its rules (default: on)")
    ap.add_argument("-n", "--dry-run", action="store_true", help="print result instead of writing")
    args = ap.parse_args(argv)

    configs = resolve_configs(args.configs, CONFIG_NAMES, accept)
    if not configs:
        return 0
    rules = RuffRules(args.ruff)
    changed = [process(c, rules, args.describe, args.dry_run) for c in configs]
    return 1 if any(changed) else 0


if __name__ == "__main__":
    sys.exit(main())
