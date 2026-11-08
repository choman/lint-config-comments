"""rumdl-config-comments, end to end on real config files."""

import sys

import pytest

from lint_config_comments.rumdl import main

from .conftest import write

CONFIG = """\
# my config
[global]
disable = ["MD040", "line-length", "MD013", "bogus"]
extend-disable = ["no-inline-html"]

[per-file-ignores]
"README.md" = ["MD057", "MD040"]

[MD013]
line-length = 120
"""

EXPECTED = """\
# my config
[global]
# rumdl rules:
#   MD013  line-length           Line length should not be excessive
#   MD040  fenced-code-language  Code blocks should have a language specified
disable = [
    "line-length",          # MD013
    "fenced-code-language", # MD040
    "bogus",
]
# rumdl rules:
#   MD033  no-inline-html  Inline HTML is not allowed
extend-disable = [
    "no-inline-html", # MD033
]

[per-file-ignores]
# rumdl rules:
#   MD040  fenced-code-language     Code blocks should have a language specified
#   MD057  existing-relative-links  Relative links should point to existing files
"README.md" = [
    "fenced-code-language",    # MD040
    "existing-relative-links", # MD057
]

[MD013]
line-length = 120
"""


def run(*args: str) -> int:
    return main(["--formatter", "none", *args])


def test_annotates_sorts_and_dedupes(repo, capsys):
    cfg = write(repo / ".config/rumdl.toml", CONFIG)
    assert run() == 1  # changed -> pre-commit sees a failure
    assert cfg.read_text() == EXPECTED
    assert "unknown rule 'bogus'" in capsys.readouterr().err


def test_idempotent(repo):
    cfg = write(repo / ".config/rumdl.toml", CONFIG)
    run()
    assert run() == 0
    assert cfg.read_text() == EXPECTED


def test_use_id(repo):
    cfg = write(repo / "rumdl.toml", '[global]\ndisable = ["line-length", "MD040"]\n')
    run("--use-id", "--no-describe")
    assert (
        cfg.read_text()
        == '[global]\ndisable = [\n    "MD013", # line-length\n    "MD040", # fenced-code-language\n]\n'
    )


def test_secondary_alias_kept_and_deduped(repo):
    """A secondary alias stays as written; the same rule listed twice is kept once."""
    cfg = write(repo / "rumdl.toml", '[global]\ndisable = ["single-h1", "MD025"]\n')
    run("--no-describe")
    assert cfg.read_text() == '[global]\ndisable = [\n    "single-h1", # MD025\n]\n'


def test_no_describe_removes_blocks(repo):
    cfg = write(repo / ".config/rumdl.toml", CONFIG)
    run()
    run("--no-describe")
    assert "# rumdl rules:" not in cfg.read_text()
    assert '"line-length",          # MD013' in cfg.read_text()


def test_cleans_up_rows_doubled_by_v0_1_0(repo):
    """v0.1.0 + toml-sort left stray rows above each list; they must go away."""
    doubled = """\
[per-file-ignores]
# MD040  fenced-code-language     Code blocks should have a language specified
# MD057  existing-relative-links  Relative links should point to existing files
# MD040  fenced-code-language     Code blocks should have a language specified
# rumdl rules:
#   MD040  fenced-code-language     Code blocks should have a language specified
"README.md" = [
    "fenced-code-language", # MD040
    "existing-relative-links", # MD057
]
"""
    cfg = write(repo / ".config/rumdl.toml", doubled)
    run()
    text = cfg.read_text()
    assert text.count("# rumdl rules:") == 1
    assert text.count("MD040  fenced-code-language") == 1


def test_dry_run_prints_without_writing(repo, capsys):
    cfg = write(repo / "rumdl.toml", CONFIG)
    assert run("-n") == 0
    assert cfg.read_text() == CONFIG
    assert capsys.readouterr().out == EXPECTED


def test_explicit_path_from_pre_commit(repo):
    cfg = write(repo / "docs/rumdl.toml", CONFIG)
    assert run(str(cfg)) == 1
    assert cfg.read_text() == EXPECTED


def test_no_config_found(repo):
    with pytest.raises(SystemExit, match="no config found"):
        run()


def test_toml_sort_style(repo):
    write(
        repo / ".pre-commit-config.yaml",
        "repos:\n  - repo: https://github.com/pappasam/toml-sort\n    rev: v0.25.0\n"
        "    hooks:\n      - id: toml-sort-fix\n        args: [--sort-inline-arrays]\n",
    )
    cfg = write(repo / ".config/rumdl.toml", '[global]\ndisable = ["MD040", "MD013"]\n')
    main([])  # auto-detect
    assert (
        cfg.read_text()
        == (
            "[global]\n"
            "# rumdl rules:\n"
            "# MD013  line-length           Line length should not be excessive\n"  # block: always by ID
            "# MD040  fenced-code-language  Code blocks should have a language specified\n"
            "disable = [\n"
            '  "fenced-code-language", # MD040\n'  # value order, 2-space indent, 1 space, no last comma
            '  "line-length" # MD013\n'
            "]\n"
        )
    )


def test_tombi_post_formats(repo):
    write(
        repo / ".pre-commit-config.yaml",
        "repos:\n  - repo: https://github.com/tombi-toml/tombi-pre-commit\n    rev: v1.10.0\n"
        "    hooks:\n      - id: tombi-format\n",
    )
    fake = write(
        repo / "fake_tombi.py",
        "import sys\nsys.stdout.write(sys.stdin.read().replace('    ', '  '))\n",
    )
    cfg = write(repo / ".config/rumdl.toml", '[global]\ndisable = ["MD040"]\n')
    main(["--tombi", f"{sys.executable} {fake}"])
    assert '  "fenced-code-language", # MD040' in cfg.read_text()
    assert main(["--tombi", f"{sys.executable} {fake}"]) == 0  # stable
