#!/bin/sh
set -eu

# Initialize the default idea brief directory for this workspace.

ideas_dir=${1:-docs/ideas}

mkdir -p "$ideas_dir"

escaped_dir=$(printf '%s' "$ideas_dir" | sed 's/\\/\\\\/g; s/"/\\"/g')

printf '{"status":"ready","directory":"%s"}\n' "$escaped_dir"
