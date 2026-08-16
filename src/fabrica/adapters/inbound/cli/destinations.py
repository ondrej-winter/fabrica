"""Argparse destination names owned by the product CLI adapter."""

COMMAND_DEST = "_fabrica_cli_command"
GLOBAL_OPTION_DESTS = frozenset(
    {
        "_fabrica_cli_print_usage",
        "_fabrica_cli_print_prices",
        "_fabrica_cli_verbose_diagnostics",
    },
)
RESERVED_DESTS = frozenset({COMMAND_DEST, *GLOBAL_OPTION_DESTS})
