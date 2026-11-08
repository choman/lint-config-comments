"""Output style, including auto-matching toml-sort when it also formats the file.

Two formatters on one file only coexist if each one's output is already what
the other would write. When toml-sort is configured to format a config (via
.pre-commit-config.yaml and/or [tool.tomlsort] in pyproject.toml), the hooks
write exactly what toml-sort would: its array indent, comment spacing,
trailing-comma rule and (with --sort-inline-arrays) its item order.
"""

import fnmatch
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import tomlkit
import yaml

TOML_SORT_HOOKS = {"toml-sort", "toml-sort-fix"}
TOMBI_HOOKS = {"tombi-format"}
TOMBI_CMD = "tombi" if shutil.which("tombi") else "uvx tombi"
PRE_COMMIT_FILES = [".pre-commit-config.yaml", ".pre-commit-config.yml"]


@dataclass
class Style:
    sort: str = "id"  # "id" (natural rule-ID order) or "value" (plain string order)
    ignore_case: bool = False  # only with sort="value"
    align: bool = True  # line up trailing comments
    comment_spaces: int = 1  # spaces before "#" when not aligning
    indent: str | None = None  # None: reuse the file's existing indent
    trailing_comma: bool = True  # comma after the last item
    block_prefix: str = (
        "#   "  # description rows; toml-sort rewrites comments to "# text"
    )
    source: str = "default"  # what the style was derived from, for messages
    tombi: str | None = (
        None  # tombi command: final output is piped through `tombi format`
    )

    @property
    def sort_mode(self) -> str:
        return "ivalue" if self.sort == "value" and self.ignore_case else self.sort


def find_root(config: Path) -> Path:
    """Directory holding .pre-commit-config.yaml (or the git root)."""
    start = config.resolve().parent
    for d in [start, *start.parents]:
        if any((d / n).is_file() for n in PRE_COMMIT_FILES) or (d / ".git").exists():
            return d
    return start


def _tomlsort_section(root: Path) -> dict:
    py = root / "pyproject.toml"
    if not py.is_file():
        return {}
    try:
        return dict(tomlkit.parse(py.read_text()).get("tool", {}).get("tomlsort", {}))
    except Exception:  # noqa: BLE001 - a broken pyproject shouldn't break this hook
        return {}


def _parse_args(args: list[str], settings: dict) -> dict:
    """Apply toml-sort CLI args on top of [tool.tomlsort] settings."""
    s = dict(settings)
    it = iter(args)
    for arg in it:
        name, _, value = arg.partition("=")
        if name in ("-a", "--all"):
            s["all"] = True
        elif name in ("-I", "--ignore-case"):
            s["ignore_case"] = True
        elif name == "--sort-inline-arrays":
            s["sort_inline_arrays"] = True
        elif name == "--trailing-comma-inline-array":
            s["trailing_comma_inline_array"] = True
        elif name in ("--spaces-before-inline-comment", "--spaces-indent-inline-array"):
            key = name.lstrip("-").replace("-", "_")
            s[key] = int(value or next(it, "0") or 0)
    return s


def _matches(rel: str, files: str | None, exclude: str | None) -> bool:
    return bool(re.search(files or "", rel)) and not (
        exclude and re.search(exclude, rel)
    )


def find_hook(config: Path, ids: set[str]) -> tuple[Path, dict] | None:
    """Return (repo root, hook) for the first pre-commit hook in `ids` that runs on config."""
    root = find_root(config)
    pc = next((root / n for n in PRE_COMMIT_FILES if (root / n).is_file()), None)
    if not pc:
        return None
    try:
        data = yaml.safe_load(pc.read_text()) or {}
    except yaml.YAMLError:
        return None

    rel = config.resolve().relative_to(root).as_posix()
    if not rel.endswith(".toml") or not _matches(
        rel, data.get("files"), data.get("exclude")
    ):
        return None
    for repo in data.get("repos", []):
        for hook in repo.get("hooks", []):
            # these formatters' hooks match by `types: [toml]`, i.e. any .toml file
            if hook.get("id") in ids and _matches(
                rel, hook.get("files"), hook.get("exclude")
            ):
                return root, hook
    return None


def detect_toml_sort(config: Path) -> dict | None:
    """Return toml-sort's effective settings if a toml-sort hook formats this file."""
    found = find_hook(config, TOML_SORT_HOOKS)
    if not found:
        return None
    root, hook = found
    args = hook.get("args", [])
    if isinstance(args, str):
        args = shlex.split(args)
    return _parse_args([str(a) for a in args], _tomlsort_section(root))


TOMBI_CONFIGS = [".tombi.toml", "tombi.toml", ".config/tombi.toml"]


def _tombi_files(root: Path) -> dict:
    """The [files] section of tombi's config, found the way tombi finds it."""
    for name in TOMBI_CONFIGS:
        p = root / name
        if p.is_file():
            return dict(tomlkit.parse(p.read_text()).get("files", {}))
    py = root / "pyproject.toml"
    if py.is_file():
        return dict(
            tomlkit.parse(py.read_text())
            .get("tool", {})
            .get("tombi", {})
            .get("files", {})
        )
    return {}


def _glob(rel: str, pattern: str) -> bool:
    pattern = pattern.removeprefix("./")
    return any(
        fnmatch.fnmatch(candidate, p)
        for candidate in (rel, rel.rsplit("/", 1)[-1])
        for p in (pattern, pattern.removeprefix("**/"))
    )


def tombi_formats(config: Path) -> bool:
    """True if a tombi-format hook runs on this file and tombi's config doesn't exclude it."""
    found = find_hook(config, TOMBI_HOOKS)
    if not found:
        return False
    root, _ = found
    rel = config.resolve().relative_to(root).as_posix()
    files = _tombi_files(root)
    include = files.get("include", ["**/*.toml"])
    exclude = files.get("exclude", [])
    return any(_glob(rel, p) for p in include) and not any(
        _glob(rel, p) for p in exclude
    )


def run_tombi(cmd: str, config: Path, text: str) -> str:
    """Format text exactly as tombi would format the file (same config, same schemas)."""
    root = find_root(config)
    rel = config.resolve().relative_to(root).as_posix()
    proc = subprocess.run(
        [*shlex.split(cmd), "format", "--quiet", "--stdin-filename", rel, "-"],
        input=text,
        capture_output=True,
        text=True,
        cwd=root,
        check=False,
    )
    if proc.returncode != 0 or not proc.stdout:
        sys.exit(
            f"error: {config}: tombi format failed, file left unchanged"
            f" (set TOMBI_OFFLINE=true if it can't reach schemastore.org)\n{proc.stderr.strip()}"
        )
    return proc.stdout


def resolve_style(
    config: Path,
    sort: str | None,
    align: bool | None,
    formatter: str = "auto",
    tombi_cmd: str = TOMBI_CMD,
) -> Style:
    """Explicit flags win; otherwise match the formatter that also formats this file.

    tombi:     output is passed through `tombi format`, so it is exactly what the
               tombi hook writes (its alignment, indent, sorting and schemas).
    toml-sort: output follows toml-sort's settings, since toml-sort rewrites
               comment spacing in ways no other layout survives.
    """
    style = Style()
    if formatter == "tombi" or (formatter == "auto" and tombi_formats(config)):
        style.tombi = tombi_cmd
        style.source = "tombi"
        if sort is not None:
            style.sort = sort
        if align is not None:
            style.align = align
        return style
    ts = detect_toml_sort(config) if formatter in ("auto", "toml-sort") else None
    if ts is not None:
        style = Style(
            sort="value" if ts.get("sort_inline_arrays") or ts.get("all") else "id",
            ignore_case=bool(ts.get("ignore_case")),
            align=False,
            comment_spaces=int(ts.get("spaces_before_inline_comment", 1)),
            indent=" " * int(ts.get("spaces_indent_inline_array", 2)),
            trailing_comma=bool(ts.get("trailing_comma_inline_array")),
            block_prefix="# ",
            source="toml-sort",
        )
    if sort is not None:
        style.sort = sort
    if align is not None:
        style.align = align
        if align and style.source == "toml-sort":
            print(
                f"warning: {config}: toml-sort formats this file and will undo --align on"
                " every run; exclude it from toml-sort to keep alignment",
                file=sys.stderr,
            )
    return style


def toml_sort_hint(config: Path) -> str:
    """One-line hint shown when the hooks change a file toml-sort also formats."""
    return (
        f"note: toml-sort formats {config}, so comments can't be aligned or indented."
        " To keep alignment, exclude it from toml-sort:\n"
        r"  exclude: ^(\.?ruff\.toml|\.config/(ruff|rumdl)\.toml)$"
    )
