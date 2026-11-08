# lint-config-comments

[![pipeline][pipeline-badge]][pipeline]
[![coverage][coverage-badge]][pipeline]
[![pytest][pytest-badge]][pytest]
[![release][release-badge]][releases]
[![python][python-badge]][pyproject]
[![pre-commit][pre-commit-badge]][pre-commit]
[![ruff][ruff-badge]][ruff]
[![uv][uv-badge]][uv]
[![conventional commits][cc-badge]][cc]

[pipeline-badge]: https://gitlab.com/choman/lint-config-comments/badges/main/pipeline.svg
[pipeline]: https://gitlab.com/choman/lint-config-comments/-/pipelines?ref=main
[coverage-badge]: https://gitlab.com/choman/lint-config-comments/badges/main/coverage.svg
[pytest-badge]: https://img.shields.io/badge/tested%20with-pytest-0A9EDC?logo=pytest&logoColor=white
[pytest]: https://docs.pytest.org
[release-badge]: https://gitlab.com/choman/lint-config-comments/-/badges/release.svg
[releases]: https://gitlab.com/choman/lint-config-comments/-/releases
[python-badge]: https://img.shields.io/badge/python-3.12%2B-blue?logo=python&logoColor=white
[pyproject]: https://gitlab.com/choman/lint-config-comments/-/blob/main/pyproject.toml
[pre-commit-badge]: https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit
[pre-commit]: https://pre-commit.com
[ruff-badge]: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json
[ruff]: https://github.com/astral-sh/ruff
[uv-badge]: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json
[uv]: https://github.com/astral-sh/uv
[cc-badge]: https://img.shields.io/badge/Conventional%20Commits-1.0.0-fe5196?logo=conventionalcommits&logoColor=white
[cc]: https://www.conventionalcommits.org

Pre-commit hooks that keep linter configs readable. Bare rule codes (`MD040`,
`E501`) are annotated with their names and descriptions. Lists are sorted,
de-duplicated and their comments aligned.

| Hook                    | Config files                                                                     |
| ----------------------- | -------------------------------------------------------------------------------- |
| `rumdl-config-comments` | `.rumdl.toml`, `rumdl.toml`, `.config/rumdl.toml`                                |
| `ruff-config-comments`  | `.ruff.toml`, `ruff.toml`, `.config/ruff.toml`, `pyproject.toml` (`[tool.ruff]`) |

[[_TOC_]]

## Usage

```yaml
repos:
  - repo: https://gitlab.com/<you>/lint-config-comments
    rev: v0.1.0
    hooks:
      - id: rumdl-config-comments
      - id: ruff-config-comments
```

The hooks rewrite the config in place, then fail so you can review and `git add`
the change. A rerun on an annotated file changes nothing.

### Pin the linter version

Rule names and descriptions come from the linter itself. Pin the linter to the
version you lint with:

```yaml
- id: ruff-config-comments
  additional_dependencies: [ruff==0.16.9]
```

### Options

Pass options with `args:`.

| Option                       | Hooks | Effect                                                                               |
| ---------------------------- | ----- | ------------------------------------------------------------------------------------ |
| `--no-describe`              | both  | Don't write the description block above each list                                    |
| `-i`, `--use-id`             | rumdl | Write `"MD040", # fenced-code-language` instead of `"fenced-code-language", # MD040` |
| `--align` / `--no-align`     | both  | Force comment alignment on or off (default: auto, see below)                         |
| `--sort id` / `--sort value` | both  | Force rule-ID or plain-string order (default: auto, see below)                       |
| `-n`, `--dry-run`            | both  | Print the result instead of writing it                                               |

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

## TOML formatters

The hooks rewrite whole rule lists, so they must agree with any TOML formatter
that also touches these files, or the two undo each other on every commit.
They detect the formatter from `.pre-commit-config.yaml` and write output it
already accepts.

### Recommended: Tombi

[Tombi](https://github.com/tombi-toml/tombi) is the recommended formatter:

|                                        | Tombi                              | toml-sort                 | Taplo                        |
| -------------------------------------- | ---------------------------------- | ------------------------- | ---------------------------- |
| Aligned trailing comments              | yes (`trailing-comment-alignment`) | no: always N spaces       | yes                          |
| Keeps indented `#   MD040` rows        | yes                                | no: rewrites to `# MD040` | yes                          |
| Per-file include/exclude in its config | yes (`[files]`, `[[overrides]]`)   | no                        | yes                          |
| Schema-aware, linter, language server  | yes                                | no                        | yes                          |
| Maintenance                            | active                             | active                    | lead maintainer stepped down |

toml-sort can't keep the layout these hooks write. It formats through a library
that resets the space before every `#` and normalizes comment text, with no
option to turn either off. Tombi keeps both and is configurable.

When a `tombi-format` hook formats a config, the hooks pass their output through
`tombi format` before writing. The result is exactly what Tombi writes, using
your Tombi config and schemas. Tombi's `[files]` include/exclude and
`[[overrides]]` with `format.enabled = false` are honored.

`.config/tombi.toml`:

```toml
toml-version = "v1.0.0"

[files]
exclude = ["uv.lock"]

[format.rules]
trailing-comment-alignment = true
trailing-comment-space-width = 2

# pyproject-fmt formats pyproject.toml; Tombi still lints it
[[overrides]]
files = { include = ["pyproject.toml"] }
format = { enabled = false }
```

Use an override, not `[files] exclude`, for files another tool formats. An
exclude also turns off `tombi-lint` for them. The hooks honor both.

`.pre-commit-config.yaml`:

```yaml
- repo: https://github.com/tombi-toml/tombi-pre-commit
  rev: v1.10.0
  hooks:
    - id: tombi-format
- repo: https://gitlab.com/choman/lint-config-comments
  rev: v0.2.0
  hooks:
    - id: ruff-config-comments
      additional_dependencies: [tombi==1.10.0] # same version as tombi-format
    - id: rumdl-config-comments
      additional_dependencies: [tombi==1.10.0]
```

Without the pin the hooks run `uvx tombi` (latest), which may format
differently from the pinned hook. Set `TOMBI_OFFLINE=true` where
schemastore.org isn't reachable.

Tombi aligns comments past the `key = [` line as well as the items, so short
lists get a wide gap. For the hooks' tighter layout, turn off Tombi formatting
for the hook-owned files:

```toml
[[overrides]]
files = { include = [".ruff.toml", ".config/rumdl.toml"] }
format = { enabled = false }
```

### toml-sort

Still supported. If a `toml-sort` or `toml-sort-fix` hook formats the config,
the hooks read its `args:`, `files:`/`exclude:` and `[tool.tomlsort]`, then
write exactly what toml-sort would:

| toml-sort setting                | Hooks then                           |
| -------------------------------- | ------------------------------------ |
| `--spaces-indent-inline-array`   | use the same indent (default 2)      |
| `--spaces-before-inline-comment` | use the same spacing, no alignment   |
| `--trailing-comma-inline-array`  | keep or drop the last comma to match |
| `--sort-inline-arrays` / `--all` | sort by value instead of rule ID     |
| `--ignore-case`                  | sort case-insensitively              |

In files toml-sort formats, comments aren't aligned and description rows
aren't indented. To get the full layout, exclude the hook-owned files:

```yaml
- id: toml-sort-fix
  exclude: ^(\.?ruff\.toml|\.config/(ruff|rumdl)\.toml)$
```

### No formatter

When no formatter touches the file, the hooks sort by rule ID, align comments
and indent the description rows. Use `--formatter none` to force this, or
`--formatter tombi` / `--formatter toml-sort` to skip detection.

## Notes

- Lines under a `# rumdl rules:` / `# ruff rules:` marker are regenerated on
  every run, so don't hand-edit them. Put your own comments elsewhere.
- Ruff does not discover `.config/ruff.toml` on its own. Point to it with
  `extend = ".config/ruff.toml"` in `pyproject.toml`, or with `--config`.
- Unknown rules or selectors are kept as-is and reported as a warning.
- Stray description rows left by v0.1.0 (see the changelog) are removed
  automatically on the next run.

## Without pre-commit

<!-- rumdl-disable -->

```bash
uvx --from git+https://gitlab.com/<you>/lint-config-comments rumdl-config-comments -n
uvx --from git+https://gitlab.com/<you>/lint-config-comments ruff-config-comments -n
```

<!-- rumdl-enable -->
