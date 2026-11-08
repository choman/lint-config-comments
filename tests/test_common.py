"""Shared helpers: paths, indents, sorting, array formatting, description blocks."""

from pathlib import Path

import pytest

from lint_config_comments.common import (
    add_rule_blocks,
    detect_indent,
    find_config,
    format_arrays,
    has_table,
    natural_key,
    remove_orphans,
    resolve_configs,
    shorten,
    sort_key,
    split_path,
    strip_rule_blocks,
    write_result,
)
from lint_config_comments.style import Style

from .conftest import write


@pytest.mark.parametrize(
    ("path", "parts"),
    [
        ("global", ("global",)),
        ("tool.ruff.lint", ("tool", "ruff", "lint")),
        ('tool.ruff."per-file-ignores"', ("tool", "ruff", "per-file-ignores")),
        ("'a.b'.c", ("a.b", "c")),
        ('"README.md"', ("README.md",)),
    ],
)
def test_split_path(path, parts):
    assert split_path(path) == parts


def test_detect_indent_uses_existing_array_indent():
    assert detect_indent('k = [\n  "a",\n  "b", # x\n]\n') == "  "
    assert detect_indent('k = [\n    "a",\n]\n') == "    "


def test_detect_indent_defaults_to_four():
    assert detect_indent('k = ["a"]\n') == "    "
    assert detect_indent("", default=2) == "  "


def test_natural_key_orders_numbers_numerically():
    codes = ["E501", "E7", "E10", "PLR2004", "B008", "E"]
    assert sorted(codes, key=natural_key) == [
        "B008",
        "E",
        "E7",
        "E10",
        "E501",
        "PLR2004",
    ]


def test_shorten():
    assert shorten("short") == "short"
    long = "x" * 100
    assert shorten(long) == "x" * 69 + "..."
    assert len(shorten(long)) == 72


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("id", ["b", "a", "Zed", "unknown"]),  # MD013 < MD040, rules without an ID last
        ("value", ["Zed", "a", "b", "unknown"]),  # plain string order, as toml-sort
        ("ivalue", ["a", "b", "unknown", "Zed"]),  # case-insensitive
    ],
)
def test_sort_key(mode, expected):
    items = [("a", "MD040"), ("unknown", None), ("b", "MD013"), ("Zed", None)]
    assert [v for v, _ in sorted(items, key=lambda vc: sort_key(mode, *vc))] == expected


ARRAY = """k = [
    "I", # isort
    "PTH", # flake8-use-pathlib
    "X",
]
"""


def test_format_arrays_aligns_comments():
    out = format_arrays(ARRAY, Style(align=True))
    assert '    "I",   # isort' in out
    assert '    "PTH", # flake8-use-pathlib' in out
    assert '    "X",\n]' in out


def test_format_arrays_fixed_spacing_and_no_trailing_comma():
    out = format_arrays(
        ARRAY, Style(align=False, comment_spaces=2, trailing_comma=False)
    )
    assert '    "I",  # isort' in out
    assert '    "PTH",  # flake8-use-pathlib' in out
    assert '    "X"\n]' in out  # last item lost its comma


def test_format_arrays_leaves_arrays_without_comments_alone():
    text = 'k = [\n    "a",\n    "b",\n]\n'
    assert format_arrays(text, Style(trailing_comma=False)) == text


MARKER = "# rumdl rules:"


def test_strip_rule_blocks_removes_marker_and_rows():
    text = f"[global]\n{MARKER}\n#   MD013  line-length  x\n# MD040  fenced  y\ndisable = [\n]\n"
    assert strip_rule_blocks(text, {MARKER}) == "[global]\ndisable = [\n]\n"


def test_strip_rule_blocks_keeps_other_comments():
    text = "# my config\n[global]\n# keep me\ndisable = []\n"
    assert strip_rule_blocks(text, {MARKER}) == text


def test_remove_orphans_drops_stray_generated_rows_only():
    text = (
        "[per-file-ignores]\n"
        "# my note about README\n"
        "# MD040  fenced-code-language  Code blocks...\n"
        "#   MD057  existing-relative-links  Relative...\n"
        '"README.md" = [\n'
        "]\n"
    )
    out = remove_orphans(text, lambda c: c in {"MD040", "MD057"})
    assert out == '[per-file-ignores]\n# my note about README\n"README.md" = [\n]\n'


def test_remove_orphans_ignores_unknown_codes_and_far_comments():
    text = "# NOTE  this  looks generated\n\nk = [\n]\n# MD040  fenced  x\n"
    assert remove_orphans(text, lambda c: c == "MD040") == text


def test_add_rule_blocks_inserts_above_each_list():
    text = '[global]\ndisable = [\n]\n\n[per-file-ignores]\n"README.md" = [\n]\n'
    items = {
        ("global", "disable"): {"MD040", "MD013"},
        ("per-file-ignores", "README.md"): {"MD057"},
    }
    rows = {
        "MD013": ("MD013", "line-length", "Line length"),
        "MD040": ("MD040", "fenced-code-language", "Code"),
        "MD057": ("MD057", "existing-relative-links", "Links"),
    }
    out = add_rule_blocks(text, items, rows.__getitem__, MARKER)
    assert out == (
        "[global]\n"
        f"{MARKER}\n"
        "#   MD013  line-length           Line length\n"
        "#   MD040  fenced-code-language  Code\n"
        "disable = [\n]\n\n"
        "[per-file-ignores]\n"
        f"{MARKER}\n"
        "#   MD057  existing-relative-links  Links\n"
        '"README.md" = [\n]\n'
    )


def test_add_rule_blocks_handles_dotted_keys():
    text = "[tool.ruff]\nlint.select = [\n]\n"
    out = add_rule_blocks(
        text,
        {("tool", "ruff", "lint", "select"): {"E"}},
        lambda s: (s, "pycodestyle Error", ""),
        "# ruff rules:",
        prefix="# ",
    )
    assert (
        out
        == "[tool.ruff]\n# ruff rules:\n# E  pycodestyle Error\nlint.select = [\n]\n"
    )


def test_find_config_walks_up_to_git_root(repo, monkeypatch):
    cfg = write(repo / ".config/rumdl.toml", "[global]\n")
    sub = repo / "a" / "b"
    sub.mkdir(parents=True)
    monkeypatch.chdir(sub)
    assert (
        find_config([".rumdl.toml", "rumdl.toml", ".config/rumdl.toml"])
        == cfg.resolve()
    )


def test_find_config_prefers_earlier_names(repo):
    write(repo / "rumdl.toml", "")
    first = write(repo / ".rumdl.toml", "")
    assert find_config([".rumdl.toml", "rumdl.toml"]) == first.resolve()


def test_has_table(repo):
    py = write(repo / "pyproject.toml", "[tool.ruff]\nline-length = 100\n")
    assert has_table(py, "tool", "ruff")
    assert not has_table(py, "tool", "tombi")


def test_resolve_configs_filters_given_paths(repo):
    a = write(repo / "pyproject.toml", "[project]\nname = 'x'\n")
    b = write(repo / "ruff.toml", "")
    assert resolve_configs(
        [a, b, Path("missing.toml")],
        ["ruff.toml"],
        lambda p: p.name != "pyproject.toml",
    ) == [b]


def test_resolve_configs_exits_when_nothing_found(repo):
    with pytest.raises(SystemExit):
        resolve_configs([], ["rumdl.toml"])


def test_write_result(repo, capsys):
    cfg = write(repo / "c.toml", "old\n")
    assert write_result(cfg, "old\n", "old\n", dry_run=False) is False
    assert write_result(cfg, "old\n", "new\n", dry_run=True) is False
    assert cfg.read_text() == "old\n"
    assert capsys.readouterr().out == "new\n"
    assert write_result(cfg, "old\n", "new\n", dry_run=False) is True
    assert cfg.read_text() == "new\n"
