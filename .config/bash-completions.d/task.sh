# shellcheck shell=bash
# Completes prek hook ids after `--` for the lint tasks:
#   task project:lint -- <TAB>

_task_prek_hooks() {
   local root
   root=$(git rev-parse --show-toplevel 2>/dev/null) || return
   if [[ -f $root/prek.toml ]]; then
      yq -p toml -r '.repos[].hooks[].id' "$root/prek.toml"
   elif [[ -f $root/.pre-commit-config.yaml ]]; then
      yq -r '.repos[].hooks[].id' "$root/.pre-commit-config.yaml"
   elif [[ -f $root/.pre-commit-config.yml ]]; then
      yq -r '.repos[].hooks[].id' "$root/.pre-commit-config.yml"
   fi 2>/dev/null | sort -u
}

_task_with_hooks() {
   if [[ $COMP_LINE =~ (^|[[:space:]])(project:|prek:|project:prek:)lint[[:space:]].*--[[:space:]] ]]; then
      mapfile -t COMPREPLY < <(compgen -W "$(_task_prek_hooks)" -- "${COMP_WORDS[COMP_CWORD]}")
      return
   fi
   _task "$@"
}

# Make sure task's own completion (which defines _task) is loaded first
declare -F _task >/dev/null || eval "$(task --completion bash)"

complete -F _task_with_hooks task
