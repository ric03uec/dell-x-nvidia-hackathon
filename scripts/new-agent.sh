#!/usr/bin/env bash
# Copy the worked example into a new agent that's a member of the root uv
# workspace (see /pyproject.toml [tool.uv.workspace]).
#
#   scripts/new-agent.sh agents/hello-agent agents/my-agent
#
# The new project gets no lockfile of its own — it resolves and locks into
# the single root uv.lock, same as every other workspace member. Do not run
# `uv lock` inside it; `just a <name> setup` (`uv sync`) picks it up via the
# workspace. The justfile derives the package name from the directory, so it
# needs no edit.
set -euo pipefail

src=${1:-}
dst=${2:-}

if [[ -z $src || -z $dst ]]; then
    echo "usage: $0 <template-dir> <new-dir>" >&2
    exit 2
fi

[[ -d $src ]] || { echo "no such template: $src" >&2; exit 2; }
[[ ! -e $dst ]] || { echo "already exists: $dst" >&2; exit 2; }

name=$(basename "$dst")
if [[ ! $name =~ ^[a-z][a-z0-9-]*$ ]]; then
    echo "agent name must be lowercase letters, digits and dashes: $name" >&2
    exit 2
fi

pkg=${name//-/_}
src_name=$(basename "$src")
src_pkg=${src_name//-/_}

excludes=(.venv uv.lock __pycache__ .pytest_cache .ruff_cache .mypy_cache)

if command -v rsync >/dev/null 2>&1; then
    rsync -a \
        --exclude '.venv' --exclude 'uv.lock' --exclude '__pycache__' \
        --exclude '.pytest_cache' --exclude '.ruff_cache' --exclude '.mypy_cache' \
        "$src/" "$dst/"
else
    # rsync not found on PATH -- install it (see docs/DESIGN.md / `just doctor`)
    # for the fast path; meanwhile fall back to a plain copy-and-prune.
    echo "warning: rsync not found on PATH; falling back to cp -a (run \`just doctor\`)" >&2
    cp -a "$src/" "$dst/"
    for ex in "${excludes[@]}"; do
        find "$dst" -depth -name "$ex" -exec rm -rf {} +
    done
fi

mv "$dst/src/$src_pkg" "$dst/src/$pkg"

# Rewrite the template's own name wherever it appears. Every file in the fresh
# copy is text (rsync excluded .venv and the lockfile), so rewrite them all
# rather than asking `grep` which ones match — `grep` on PATH may be ugrep or
# BSD grep, whose -Z/--null flags disagree, and the mismatch fails silently.
# sed -i is likewise not portable, so write beside the file and move into place.
while IFS= read -r file; do
    sed -e "s/$src_name/$name/g" -e "s/$src_pkg/$pkg/g" "$file" >"$file.tmp"
    mv "$file.tmp" "$file"
done < <(find "$dst" -type f)

# The rename pass above only catches literal occurrences of the template's own
# name. Two known spots describe the TEMPLATE ITSELF (that this project is the
# worked example / that `just new` copies it) rather than the agent being
# scaffolded, so substitution alone can't fix them — replace them outright
# with per-agent text.
pyproject="$dst/pyproject.toml"
if [[ -f $pyproject ]]; then
    sed -e "s/^description = .*/description = \"$name NemoClaw agent project.\"/" \
        "$pyproject" >"$pyproject.tmp"
    mv "$pyproject.tmp" "$pyproject"
fi

app_py="$dst/src/$pkg/app.py"
if [[ -f $app_py ]]; then
    sed -e "1s/.*/\"\"\"$name's HTTP surface.\"\"\"/" "$app_py" >"$app_py.tmp"
    mv "$app_py.tmp" "$app_py"
fi

echo "created $dst"
echo "next:  just a $name setup && just a $name test"
