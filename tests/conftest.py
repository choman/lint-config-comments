"""Shared fixtures.

The hooks get rule data from `rumdl rule -o json` and `ruff rule/linter`.
Unit tests use a small fixed rule set (taken from rumdl 0.3.2 / ruff 0.16.9)
so results don't change with tool versions and nothing needs the network.
"""

import json
from pathlib import Path

import pytest

RUMDL_RULES = [
    {
        "code": "MD013",
        "name": "line-length",
        "aliases": [],
        "summary": "Line length should not be excessive",
    },
    {
        "code": "MD024",
        "name": "no-duplicate-heading",
        "aliases": [],
        "summary": "Multiple headings with the same content",
    },
    {
        "code": "MD025",
        "name": "single-title",
        "aliases": ["single-h1"],
        "summary": "Multiple top-level headings in the same document",
    },
    {
        "code": "MD033",
        "name": "no-inline-html",
        "aliases": [],
        "summary": "Inline HTML is not allowed",
    },
    {
        "code": "MD040",
        "name": "fenced-code-language",
        "aliases": [],
        "summary": "Code blocks should have a language specified",
    },
    {
        "code": "MD057",
        "name": "existing-relative-links",
        "aliases": [],
        "summary": "Relative links should point to existing files",
    },
]

RUFF_RULES = [
    {
        "code": "E501",
        "name": "line-too-long",
        "summary": "Line too long ({width} > {limit})",
    },
    {
        "code": "E701",
        "name": "multiple-statements-on-one-line-colon",
        "summary": "Multiple statements on one line (colon)",
    },
    {
        "code": "F401",
        "name": "unused-import",
        "summary": "`{name}` imported but unused",
    },
    {
        "code": "I001",
        "name": "unsorted-imports",
        "summary": "Import block is un-sorted or un-formatted",
    },
    {
        "code": "PTH100",
        "name": "os-path-abspath",
        "summary": "`os.path.abspath()` should be replaced by `Path.resolve()`",
    },
    {
        "code": "PLR2004",
        "name": "magic-value-comparison",
        "summary": "Magic value used in comparison, consider replacing `{value}` with a constant variable",
    },
    {
        "code": "B008",
        "name": "function-call-in-default-argument",
        "summary": "Do not perform function call `{name}` in argument defaults; instead, perform the call within the function",
    },
    {"code": "S101", "name": "assert", "summary": "Use of `assert` detected"},
    {
        "code": "UP006",
        "name": "non-pep585-annotation",
        "summary": "Use `{to}` instead of `{from}` for type annotation",
    },
    {
        "name": "removed-rule-without-code",
        "summary": "rules ruff reports without a code are ignored",
    },
]

RUFF_LINTERS = [
    {
        "prefix": "",
        "name": "pycodestyle",
        "categories": [
            {"prefix": "E", "name": "Error"},
            {"prefix": "W", "name": "Warning"},
        ],
    },
    {"prefix": "F", "name": "Pyflakes"},
    {"prefix": "I", "name": "isort"},
    {"prefix": "PTH", "name": "flake8-use-pathlib"},
    {
        "prefix": "PL",
        "name": "Pylint",
        "categories": [
            {"prefix": "C", "name": "Convention"},
            {"prefix": "R", "name": "Refactor"},
        ],
    },
    {"prefix": "B", "name": "flake8-bugbear"},
    {"prefix": "S", "name": "flake8-bandit"},
    {"prefix": "UP", "name": "pyupgrade"},
]


def fake_check_output(cmd, **_kwargs):
    """Stand-in for subprocess.check_output answering rumdl/ruff rule queries."""
    args = list(cmd)
    if "rumdl" in args[0] and args[1:3] == ["rule", "-o"]:
        data = RUMDL_RULES
    elif "ruff" in args[0] and args[1] == "rule":
        data = RUFF_RULES
    elif "ruff" in args[0] and args[1] == "linter":
        data = RUFF_LINTERS
    else:  # pragma: no cover - a test asked for something unexpected
        raise AssertionError(f"unexpected command: {args}")
    return json.dumps(data)


@pytest.fixture(autouse=True)
def fake_tools(request, monkeypatch):
    """Every unit test sees the fixed rule data; integration tests use the real tools."""
    if request.node.get_closest_marker("integration"):
        return
    from lint_config_comments import ruff, rumdl

    monkeypatch.setattr(rumdl.subprocess, "check_output", fake_check_output)
    monkeypatch.setattr(ruff.subprocess, "check_output", fake_check_output)


@pytest.fixture
def repo(tmp_path, monkeypatch) -> Path:
    """An empty repo as the working directory.

    The hooks only look for a .git directory to find the repo root, so an
    empty one is enough (and git needn't be installed, e.g. in slim CI images).
    """
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    return tmp_path


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


@pytest.fixture
def rumdl_rules():
    from lint_config_comments.rumdl import RumdlRules

    return RumdlRules("rumdl")


@pytest.fixture
def ruff_rules():
    from lint_config_comments.ruff import RuffRules

    return RuffRules("ruff")
