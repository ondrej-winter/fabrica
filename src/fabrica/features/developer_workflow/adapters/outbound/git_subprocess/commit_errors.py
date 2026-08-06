"""Safe adapter-local error messages for approved git commit failures."""

DECODE_ERROR_MESSAGE = "git commit output could not be decoded as UTF-8"
GIT_COMMIT_FAILED_MESSAGE = "git commit failed"
GIT_COMMIT_START_FAILED_MESSAGE = "git commit failed to start"
GIT_COMMIT_TIMED_OUT_MESSAGE = "git commit timed out"
GIT_UNAVAILABLE_MESSAGE = "git executable is unavailable"
NO_STAGED_CHANGES_MESSAGE = "no staged git changes were available to commit"
NOT_REPOSITORY_MESSAGE = "current directory is not inside a git repository"
