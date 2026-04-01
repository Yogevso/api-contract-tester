"""Exit codes for the CLI."""

from enum import IntEnum


class ExitCode(IntEnum):
    SUCCESS = 0
    TEST_FAILURE = 1
    CONFIG_ERROR = 2
    RUNTIME_ERROR = 3
