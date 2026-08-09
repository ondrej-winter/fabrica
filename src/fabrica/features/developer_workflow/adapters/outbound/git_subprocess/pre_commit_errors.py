"""Safe adapter-local error messages for pre-commit execution."""

DECODE_ERROR_MESSAGE = "pre-commit output could not be decoded as UTF-8"
NOT_REPOSITORY_MESSAGE = "current directory is not inside a git repository"
OVERSIZED_OUTPUT_MESSAGE = "pre-commit output exceeded the configured bound"
PRE_COMMIT_START_FAILED_MESSAGE = "pre-commit failed to start"
PRE_COMMIT_TIMED_OUT_MESSAGE = "pre-commit timed out"
PRE_COMMIT_UNAVAILABLE_MESSAGE = "pre-commit executable is unavailable"
