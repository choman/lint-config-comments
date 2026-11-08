"""Against the real tools: the configs still load, and formatters agree with the hooks.

Skipped for any tool that isn't installed (they're in the dev dependency group).
"""

import shutil
import subprocess

import pytest

from lint_config_comments import ruff, rumdl

from .conftest import write

pytestmark = pytest.mark.integration


def needs(tool: str):
    return pytest.mark.skipif(
        shutil.which(tool) is None, reason=f"{tool} not installed"
    )


def ok(*cmd: str) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, (
        f"{' '.join(cmd)} failed:\n{proc.stdout}\n{proc.stderr}"
    )
    return proc


RUMDL_CONFIG = '[global]\ndisable = ["MD040", "MD013"]\n\n[per-file-ignores]\n"README.md" = ["MD057", "MD040"]\n'
RUFF_CONFIG = '[lint]\nextend-select = ["PTH", "I"]\nignore = ["E501"]\n'


@needs("rumdl")
def test_rumdl_accepts_annotated_config(repo):
    cfg = write(repo / ".config/rumdl.toml", RUMDL_CONFIG)
    assert rumdl.main(["--formatter", "none", "--rumdl", "rumdl"]) == 1
    assert "fenced-code-language" in cfg.read_text()
    shown = ok("rumdl", "config", "--config", str(cfg)).stdout
    assert "MD040" in shown
    assert rumdl.main(["--formatter", "none", "--rumdl", "rumdl"]) == 0


@needs("ruff")
def test_ruff_accepts_annotated_config(repo):
    cfg = write(repo / ".ruff.toml", RUFF_CONFIG)
    assert ruff.main(["--formatter", "none", "--ruff", "ruff"]) == 1
    settings = ok("ruff", "check", "--config", str(cfg), "--show-settings", ".").stdout
    assert "flake8-use-pathlib" in settings or "PTH" in settings
    assert ruff.main(["--formatter", "none", "--ruff", "ruff"]) == 0


TOMBI_PRECOMMIT = """\
repos:
  - repo: https://github.com/tombi-toml/tombi-pre-commit
    rev: v1.10.0
    hooks:
      - id: tombi-format
"""


@needs("tombi")
@needs("ruff")
@needs("rumdl")
@pytest.mark.parametrize(
    "tombi_toml",
    [
        "",  # tombi defaults
        "[format.rules]\nindent-width = 4\ntrailing-comment-alignment = true\ntrailing-comment-space-width = 2\n",
    ],
)
def test_tombi_agrees(repo, monkeypatch, tombi_toml):
    monkeypatch.setenv("TOMBI_OFFLINE", "true")
    write(repo / ".pre-commit-config.yaml", TOMBI_PRECOMMIT)
    write(repo / ".config/tombi.toml", 'toml-version = "v1.0.0"\n' + tombi_toml)
    rcfg = write(repo / ".config/rumdl.toml", RUMDL_CONFIG)
    fcfg = write(repo / ".ruff.toml", RUFF_CONFIG)
    rumdl.main(["--rumdl", "rumdl", "--tombi", "tombi"])
    ruff.main(["--ruff", "ruff", "--tombi", "tombi"])
    ok("tombi", "format", "--check", str(rcfg), str(fcfg))  # tombi would change nothing
    assert rumdl.main(["--rumdl", "rumdl", "--tombi", "tombi"]) == 0
    assert ruff.main(["--ruff", "ruff", "--tombi", "tombi"]) == 0


TOML_SORT_PRECOMMIT = """\
repos:
  - repo: https://github.com/pappasam/toml-sort
    rev: v0.25.0
    hooks:
      - id: toml-sort-fix
        args: [{args}]
"""


@needs("toml-sort")
@needs("rumdl")
@pytest.mark.parametrize(
    "args",
    [
        [],
        [
            "--sort-inline-arrays",
            "--trailing-comma-inline-array",
            "--spaces-indent-inline-array=4",
        ],
        ["--all", "--ignore-case", "--spaces-before-inline-comment", "2"],
    ],
)
def test_toml_sort_agrees(repo, args):
    write(
        repo / ".pre-commit-config.yaml",
        TOML_SORT_PRECOMMIT.format(args=", ".join(f'"{a}"' for a in args)),
    )
    cfg = write(repo / ".config/rumdl.toml", RUMDL_CONFIG)
    rumdl.main(["--rumdl", "rumdl"])
    ok("toml-sort", "--check", *args, str(cfg))  # toml-sort would change nothing
    assert rumdl.main(["--rumdl", "rumdl"]) == 0
