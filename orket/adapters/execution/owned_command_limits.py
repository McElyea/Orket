"""Shared limits for the package transport and its isolated supervisor process."""
DEFAULT_OUTPUT_LIMIT = 4 * 1024 * 1024
MAX_OUTPUT_LIMIT = 64 * 1024 * 1024


def output_limit_bytes(value: int | None) -> int:
    if value is None:
        return DEFAULT_OUTPUT_LIMIT
    if type(value) is not int or not 1 <= value <= MAX_OUTPUT_LIMIT:
        raise ValueError("E_COMMAND_OUTPUT_LIMIT_INVALID")
    return value
