"""ruff-config-comments: selector descriptions and end-to-end rewrites."""

import pytest
import tomlkit

from lint_config_comments.ruff import accept, lint_tables, main

from .conftest import write


@pytest.mark.parametrize(
    ("selector", "label"),
    [
        ("E501", "line-too-long"),  # exact rule
        ("F", "Pyflakes"),  # linter prefix
        ("E", "pycodestyle Error"),  # category of a prefix-less linter
        ("PLR", "Pylint Refactor"),  # linter prefix + category
        ("PL", "Pylint"),
        ("E5", "pycodestyle Error (1 rules)"),  # partial prefix
        ("ALL", "ALL"),
    ],
)
def test_describe(ruff_rules, selector, label):
    assert ruff_rules.describe(selector)[0] == label


def test_describe_unknown(ruff_rules):
    assert ruff_rules.describe("XYZ999") is None


def test_rules_without_code_are_ignored(ruff_rules):
    assert all(code for code in ruff_rules.rules)


def test_accept(repo):
    assert accept(write(repo / ".ruff.toml", ""))
    assert not accept(write(repo / "pyproject.toml", "[project]\nname = 'x'\n"))
    assert accept(write(repo / "pyproject.toml", "[tool.ruff]\nline-length = 100\n"))


def test_lint_tables():
    doc = tomlkit.parse("[tool.ruff]\nselect = []\n[tool.ruff.lint]\nignore = []\n")
    assert [path for path, _ in lint_tables(doc, is_pyproject=True)] == [
        ("tool", "ruff"),
        ("tool", "ruff", "lint"),
    ]
    doc = tomlkit.parse("[lint]\nselect = []\n")
    assert [path for path, _ in lint_tables(doc, is_pyproject=False)] == [(), ("lint",)]


def run(*args: str) -> int:
    return main(["--formatter", "none", *args])


def test_ruff_toml(repo, capsys):
    cfg = write(
        repo / ".ruff.toml",
        '[lint]\nextend-select = ["PTH", "I", "XYZ999"]\nignore = ["E501", "B008"]\n',
    )
    assert run() == 1
    assert cfg.read_text() == (
        "[lint]\n"
        "# ruff rules:\n"
        "#   I    isort\n"
        "#   PTH  flake8-use-pathlib\n"
        "extend-select = [\n"
        '    "I",   # isort\n'
        '    "PTH", # flake8-use-pathlib\n'
        '    "XYZ999",\n'
        "]\n"
        "# ruff rules:\n"
        "#   B008  function-call-in-default-argument  Do not perform function call `{name}` in argument defaults; instead,...\n"
        "#   E501  line-too-long                      Line too long ({width} > {limit})\n"
        "ignore = [\n"
        '    "B008", # function-call-in-default-argument\n'
        '    "E501", # line-too-long\n'
        "]\n"
    )
    assert "unknown selector 'XYZ999'" in capsys.readouterr().err
    assert run() == 0  # idempotent


def test_pyproject_with_per_file_ignores(repo):
    cfg = write(
        repo / "pyproject.toml",
        '[project]\nname = "x"\n\n[tool.ruff.lint]\nselect = ["UP", "E", "F"]\n\n'
        '[tool.ruff.lint.per-file-ignores]\n"tests/*" = ["S101", "PLR2004"]\n',
    )
    run()
    assert cfg.read_text() == (
        '[project]\nname = "x"\n\n'
        "[tool.ruff.lint]\n"
        "# ruff rules:\n"
        "#   E   pycodestyle Error\n"
        "#   F   Pyflakes\n"
        "#   UP  pyupgrade\n"
        "select = [\n"
        '    "E",  # pycodestyle Error\n'
        '    "F",  # Pyflakes\n'
        '    "UP", # pyupgrade\n'
        "]\n\n"
        "[tool.ruff.lint.per-file-ignores]\n"
        "# ruff rules:\n"
        "#   PLR2004  magic-value-comparison  Magic value used in comparison, consider replacing `{value}` with a c...\n"
        "#   S101     assert                  Use of `assert` detected\n"
        '"tests/*" = [\n'
        '    "PLR2004", # magic-value-comparison\n'
        '    "S101",    # assert\n'
        "]\n"
    )


def test_pyproject_fmt_dotted_keys_and_indent(repo):
    """pyproject-fmt writes `lint.select` under [tool.ruff] with 2-space arrays."""
    cfg = write(
        repo / "pyproject.toml",
        '[project]\nname = "x"\nclassifiers = [\n  "Programming Language :: Python",\n]\n\n'
        '[tool.ruff]\nlint.select = [ "I", "E" ]\n',
    )
    run()
    text = cfg.read_text()
    assert (
        "# ruff rules:\n#   E  pycodestyle Error\n#   I  isort\nlint.select = [" in text
    )
    assert (
        '\n  "E", # pycodestyle Error\n  "I", # isort\n' in text
    )  # reused the 2-space indent
    assert run() == 0


def test_pyproject_without_ruff_is_skipped(repo):
    py = write(
        repo / "pyproject.toml", '[project]\nname = "x"\ndependencies = ["b", "a"]\n'
    )
    assert run(str(py)) == 0
    assert py.read_text() == '[project]\nname = "x"\ndependencies = ["b", "a"]\n'
