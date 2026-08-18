"""Argparse destination names reserved by the product CLI shell.

Feature command parsers must not use these destinations. The shell writes them
while parsing shared state, removes them before feature decoders run, and rejects
feature-owned arguments that would collide with them.
"""

COMMAND_DEST = "_fabrica_cli_command"
GLOBAL_OPTION_DESTS = frozenset(
    {
        "_fabrica_cli_print_usage",
        "_fabrica_cli_print_prices",
        "_fabrica_cli_verbose_diagnostics",
    },
)
RESERVED_DESTS = frozenset({COMMAND_DEST, *GLOBAL_OPTION_DESTS})
