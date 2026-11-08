"""Formatter detection: toml-sort and Tombi, from .pre-commit-config.yaml and their configs."""

import sys

import pytest

from lint_config_comments.style import (
    _glob,
    _parse_args,
    detect_toml_sort,
    find_hook,
    resolve_style,
    run_tombi,
    tombi_formats,
)

from .conftest import write

TOML_SORT = """\
repos:
  - repo: https://github.com/pappasam/toml-sort
    rev: v0.25.0
    hooks:
      - id: toml-sort-fix
{extra}
"""

TOMBI = """\
repos:
  - repo: https://github.com/tombi-toml/tombi-pre-commit
    rev: v1.10.0
    hooks:
      - id: tombi-format
{extra}
"""


def precommit(repo, template, extra=""):
    write(repo / ".pre-commit-config.yaml", template.format(extra=extra))


# ─── toml-sort ──────────────────────────────────────────────────────────────


def test_parse_args_flags_and_values():
    settings = _parse_args(
        [
            "--in-place",
            "--sort-inline-arrays",
            "-I",
            "--trailing-comma-inline-array",
            "--spaces-indent-inline-array=4",
            "--spaces-before-inline-comment",
            "2",
        ],
        {},
    )
    assert settings == {
        "sort_inline_arrays": True,
        "ignore_case": True,
        "trailing_comma_inline_array": True,
        "spaces_indent_inline_array": 4,
        "spaces_before_inline_comment": 2,
    }


def test_parse_args_overrides_tool_tomlsort():
    assert (
        _parse_args(
            ["--spaces-indent-inline-array", "4"], {"spaces_indent_inline_array": 2}
        )["spaces_indent_inline_array"]
        == 4
    )


def test_no_precommit_config_means_no_formatter(repo):
    cfg = write(repo / ".ruff.toml", "")
    assert detect_toml_sort(cfg) is None
    assert not tombi_formats(cfg)
    assert resolve_style(cfg, None, None).source == "default"


def test_toml_sort_detected_with_its_settings(repo):
    precommit(
        repo,
        TOML_SORT,
        "        args: [--sort-inline-arrays, --trailing-comma-inline-array, --spaces-indent-inline-array=4]",
    )
    cfg = write(repo / ".ruff.toml", "")
    style = resolve_style(cfg, None, None)
    assert style.source == "toml-sort"
    assert (
        style.sort,
        style.align,
        style.indent,
        style.trailing_comma,
        style.block_prefix,
    ) == ("value", False, "    ", True, "# ")


def test_toml_sort_reads_tool_tomlsort(repo):
    precommit(repo, TOML_SORT)
    write(
        repo / "pyproject.toml",
        "[tool.tomlsort]\nspaces_before_inline_comment = 2\nignore_case = true\nall = true\n",
    )
    style = resolve_style(write(repo / ".ruff.toml", ""), None, None)
    assert (style.comment_spaces, style.sort_mode, style.indent) == (2, "ivalue", "  ")


@pytest.mark.parametrize(
    ("extra", "detected"),
    [
        ("        exclude: ^\\.ruff\\.toml$", False),
        ("        files: ^pyproject\\.toml$", False),
        ("        files: \\.toml$", True),
    ],
)
def test_toml_sort_files_and_exclude(repo, extra, detected):
    precommit(repo, TOML_SORT, extra)
    assert (detect_toml_sort(write(repo / ".ruff.toml", "")) is not None) is detected


def test_top_level_exclude_applies(repo):
    write(
        repo / ".pre-commit-config.yaml",
        "exclude: ^\\.ruff\\.toml$\n" + TOML_SORT.format(extra=""),
    )
    assert find_hook(write(repo / ".ruff.toml", ""), {"toml-sort-fix"}) is None


def test_explicit_flags_win(repo):
    precommit(repo, TOML_SORT, "        args: [--sort-inline-arrays]")
    style = resolve_style(write(repo / ".ruff.toml", ""), "id", True)
    assert (style.sort, style.align) == ("id", True)


def test_formatter_none_skips_detection(repo):
    precommit(repo, TOML_SORT)
    assert (
        resolve_style(
            write(repo / ".ruff.toml", ""), None, None, formatter="none"
        ).source
        == "default"
    )


# ─── Tombi ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("rel", "pattern", "matches"),
    [
        (".ruff.toml", ".ruff.toml", True),
        (".config/rumdl.toml", ".config/rumdl.toml", True),
        (".config/rumdl.toml", "**/rumdl.toml", True),
        ("sub/pyproject.toml", "pyproject.toml", True),
        ("a/b.toml", "**/*.toml", True),
        ("b.toml", "**/*.toml", True),
        ("uv.lock", "**/*.toml", False),
    ],
)
def test_glob(rel, pattern, matches):
    assert _glob(rel, pattern) is matches


def test_tombi_detected(repo):
    precommit(repo, TOMBI)
    cfg = write(repo / ".ruff.toml", "")
    assert tombi_formats(cfg)
    assert resolve_style(cfg, None, None, tombi_cmd="tombi").tombi == "tombi"


@pytest.mark.parametrize(
    ("tombi_toml", "formats"),
    [
        ('[files]\nexclude = [".ruff.toml"]\n', False),
        ('[files]\ninclude = ["other/**/*.toml"]\n', False),
        (
            '[[overrides]]\nfiles = { include = [".ruff.toml"] }\nformat = { enabled = false }\n',
            False,
        ),
        (
            '[[overrides]]\nfiles = { include = ["pyproject.toml"] }\nformat = { enabled = false }\n',
            True,
        ),
        (
            '[format]\nenabled = false\n[[overrides]]\nfiles = { include = [".ruff.toml"] }\nformat = { enabled = true }\n',
            True,
        ),
    ],
)
def test_tombi_config_files_and_overrides(repo, tombi_toml, formats):
    precommit(repo, TOMBI)
    write(repo / ".config/tombi.toml", tombi_toml)
    assert tombi_formats(write(repo / ".ruff.toml", "")) is formats


def test_tombi_config_in_pyproject(repo):
    precommit(repo, TOMBI)
    write(repo / "pyproject.toml", '[tool.tombi.files]\nexclude = [".ruff.toml"]\n')
    assert not tombi_formats(write(repo / ".ruff.toml", ""))


def test_tombi_hook_exclude(repo):
    precommit(repo, TOMBI, "        exclude: ^\\.ruff\\.toml$")
    assert not tombi_formats(write(repo / ".ruff.toml", ""))


def test_tombi_wins_over_toml_sort(repo):
    write(
        repo / ".pre-commit-config.yaml",
        TOMBI.format(extra="") + TOML_SORT.split("repos:\n", 1)[1].format(extra=""),
    )
    assert resolve_style(write(repo / ".ruff.toml", ""), None, None).source == "tombi"


FAKE_TOMBI = """\
import sys
args = sys.argv[1:]
assert args[:4] == ["format", "--quiet", "--stdin-filename", ".ruff.toml"], args
text = sys.stdin.read()
sys.stdout.write(text if text.startswith("# tombi") else "# tombi\\n" + text)
"""


def test_run_tombi_pipes_through_and_passes_filename(repo):
    script = write(repo / "fake_tombi.py", FAKE_TOMBI)
    cfg = write(repo / ".ruff.toml", "")
    assert run_tombi(f"{sys.executable} {script}", cfg, "a = 1\n") == "# tombi\na = 1\n"


def test_run_tombi_failure_exits(repo):
    script = write(repo / "fail.py", "import sys; sys.exit(2)\n")
    with pytest.raises(SystemExit, match="tombi format failed"):
        run_tombi(
            f"{sys.executable} {script}", write(repo / ".ruff.toml", ""), "a = 1\n"
        )
