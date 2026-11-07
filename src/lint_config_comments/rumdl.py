"""Annotate rule lists in a rumdl config with aliases/IDs and descriptions."""

import argparse
import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import tomlkit

from .common import (
    Items, add_rule_blocks, align_comments, natural_key,
    resolve_configs, strip_rule_blocks, write_result,
)

DEFAULT_CMD = "rumdl" if shutil.which("rumdl") else "uvx rumdl"
CONFIG_NAMES = [".rumdl.toml", "rumdl.toml", ".config/rumdl.toml"]
RULE_LIST_KEYS = {"disable", "enable", "extend-disable", "extend-enable", "fixable", "unfixable"}
MARKER = "# rumdl rules:"
OLD_MARKERS = {MARKER, "# rumdl rules in this section:"}


class RumdlRules:
    def __init__(self, cmd: str = DEFAULT_CMD):
        data = json.loads(subprocess.check_output([*shlex.split(cmd), "rule", "-o", "json"], text=True))
        self.id_to_alias = {r["code"]: r["name"] for r in data}
        self.summary = {r["code"]: r.get("summary", "") for r in data}
        self.alias_to_id = {}
        for r in data:
            for name in [r["name"], *r.get("aliases", [])]:
                self.alias_to_id[name.lower()] = r["code"]

    def resolve(self, rule: str) -> tuple[str, str | None]:
        """Return (alias, id) for an ID or alias; id is None if unknown."""
        if rule.upper() in self.id_to_alias:
            return self.id_to_alias[rule.upper()], rule.upper()
        return rule, self.alias_to_id.get(rule.lower())

    def row(self, code: str) -> tuple[str, str, str]:
        return code, self.id_to_alias[code], self.summary.get(code, "")


def rewrite(arr, rules: RumdlRules, use_id: bool, seen: set):
    new = tomlkit.array().multiline(True)
    resolved = {}
    for item in arr:
        alias, code = rules.resolve(str(item))
        resolved.setdefault(code or str(item), (alias, code))
    for alias, code in sorted(resolved.values(), key=lambda ac: (ac[1] is None, natural_key(ac[1] or ac[0]))):
        if code:
            seen.add(code)
            value, comment = (code, alias) if use_id else (alias, code)
            new.add_line(value, comment=comment)
        else:
            print(f"warning: unknown rule {alias!r}, left as-is", file=sys.stderr)
            new.add_line(alias)
    return new


def process(config: Path, rules: RumdlRules, use_id: bool, describe: bool, dry_run: bool) -> bool:
    original = config.read_text()
    doc = tomlkit.parse(strip_rule_blocks(original, OLD_MARKERS))
    items: Items = {}

    glob = doc.get("global", {})
    for key in RULE_LIST_KEYS & set(glob):
        glob[key] = rewrite(glob[key], rules, use_id, items.setdefault(("global", key), set()))
    pfi = doc.get("per-file-ignores", {})
    for pattern in list(pfi):
        pfi[pattern] = rewrite(pfi[pattern], rules, use_id, items.setdefault(("per-file-ignores", pattern), set()))

    out = align_comments(tomlkit.dumps(doc))
    if describe:
        out = add_rule_blocks(out, items, rules.row, MARKER)
    return write_result(config, original, out, dry_run)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("configs", nargs="*", type=Path, help=f"config files (default: search for {', '.join(CONFIG_NAMES)})")
    ap.add_argument("--rumdl", default=DEFAULT_CMD, help=f"rumdl command (default: {DEFAULT_CMD!r})")
    ap.add_argument("-i", "--use-id", action="store_true", help="write rule IDs with the alias as the comment")
    ap.add_argument("-d", "--describe", action=argparse.BooleanOptionalAction, default=True,
                    help="comment block above each rule list describing its rules (default: on)")
    ap.add_argument("-n", "--dry-run", action="store_true", help="print result instead of writing")
    args = ap.parse_args(argv)

    configs = resolve_configs(args.configs, CONFIG_NAMES)
    if not configs:
        return 0
    rules = RumdlRules(args.rumdl)
    changed = [process(c, rules, args.use_id, args.describe, args.dry_run) for c in configs]
    return 1 if any(changed) else 0


if __name__ == "__main__":
    sys.exit(main())
