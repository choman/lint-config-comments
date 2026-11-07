# lint-config-comments

Pre-commit hooks that keep linter configs readable. Bare rule codes (`MD040`, `E501`) are annotated with their names and descriptions. Lists are sorted, de-duplicated and their comments aligned.

| Hook | Config files |
| --- | --- |
| `rumdl-config-comments` | `.rumdl.toml`, `rumdl.toml`, `.config/rumdl.toml` |
| `ruff-config-comments` | `.ruff.toml`, `ruff.toml`, `.config/ruff.toml`, `pyproject.toml` (`[tool.ruff]`) |

## Usage

```yaml
repos:
  - repo: https://gitlab.com/<you>/lint-config-comments
    rev: v0.1.0
    hooks:
      - id: rumdl-config-comments
      - id: ruff-config-comments
```

The hooks rewrite the config in place, then fail so you can review and `git add` the change. A rerun on an annotated file changes nothing.

### Pin the linter version

Rule names and descriptions come from the linter itself. Pin the linter to the version you lint with:

```yaml
      - id: ruff-config-comments
        additional_dependencies: [ruff==0.16.9]
```

### Options

Pass options with `args:`.

| Option | Hooks | Effect |
| --- | --- | --- |
| `--no-describe` | both | Don't write the description block above each list |
| `-i`, `--use-id` | rumdl | Write `"MD040", # fenced-code-language` instead of `"fenced-code-language", # MD040` |
| `-n`, `--dry-run` | both | Print the result instead of writing it |

```yaml
      - id: rumdl-config-comments
        args: [--use-id]
```

## Example

### rumdl (default: aliases as values)

```toml
[global]
# rumdl rules:
#   MD013  line-length           Line length should not be excessive
#   MD040  fenced-code-language  Code blocks should have a language specified
disable = [
    "line-length",          # MD013
    "fenced-code-language", # MD040
]
```

### ruff (codes stay as values, since ruff does not accept rule names)

```toml
[tool.ruff.lint]
# ruff rules:
#   B    flake8-bugbear
#   E    pycodestyle Error
#   UP   pyupgrade
select = [
    "B",  # flake8-bugbear
    "E",  # pycodestyle Error
    "UP", # pyupgrade
]
```

## Notes

- Lines under a `# rumdl rules:` / `# ruff rules:` marker are regenerated on every run, so don't hand-edit them. Put your own comments elsewhere.
- Ruff does not discover `.config/ruff.toml` on its own. Point to it with `extend = ".config/ruff.toml"` in `pyproject.toml`, or with `--config`.
- Unknown rules or selectors are kept as-is and reported as a warning.

## Without pre-commit

```bash
uvx --from git+https://gitlab.com/<you>/lint-config-comments rumdl-config-comments -n
uvx --from git+https://gitlab.com/<you>/lint-config-comments ruff-config-comments -n
```
