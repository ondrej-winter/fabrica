"""Fixed git command definitions for repository snapshot observations."""

DEFAULT_GIT_REPOSITORY_SNAPSHOT_TIMEOUT_SECONDS = 10.0
DEFAULT_MAX_GIT_REPOSITORY_SNAPSHOT_OUTPUT_BYTES = 500_000

GIT_WRITE_TREE_ARGV = ("git", "--no-pager", "write-tree")
GIT_TRACKED_WORKTREE_DIFF_ARGV = (
    "git",
    "-c",
    "core.pager=cat",
    "-c",
    "core.quotePath=false",
    "-c",
    "color.ui=false",
    "--no-pager",
    "diff",
    "--no-ext-diff",
    "--no-textconv",
    "--no-renames",
    "--no-color",
    "--binary",
    "--ignore-submodules=none",
)
