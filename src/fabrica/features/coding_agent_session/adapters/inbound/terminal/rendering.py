"""Safe, bounded terminal rendering for coding-agent host decisions."""

from typing import TextIO

from fabrica.adapters.inbound.cli.rendering import bound_multiline_text, bound_text, write_line
from fabrica.features.workspace_command_execution.application.dtos import CommandExecutionMode, PlannedCommand
from fabrica.features.workspace_editing.application.dtos import PatchPlan


def write_question(stream: TextIO, question: str, options: tuple[str, ...]) -> None:
    """Render one visibly distinct structured question and its options."""
    write_line(stream, "Question:")
    write_line(stream, question)
    for index, option in enumerate(options, start=1):
        write_line(stream, f"  {index}. {option}")


def write_command_preview(stream: TextIO, command: PlannedCommand) -> None:
    """Render only the safe resolved-command fields needed for approval."""
    write_line(stream, "Command approval required:")
    write_line(stream, f"Command: {_command_text(command)}")
    write_line(stream, f"Workspace directory: {command.resolved_cwd}")
    write_line(stream, f"Timeout: {command.request.timeout_ms} ms")


def write_patch_preview(stream: TextIO, plan: PatchPlan) -> None:
    """Render the immutable patch preview, paths, derived effects, and digest."""
    write_line(stream, "Patch approval required:")
    if plan.approval_preview is not None:
        write_line(stream, "Planned changes:")
        stream.write(bound_multiline_text(plan.approval_preview.text))
        if not plan.approval_preview.text.endswith("\n"):
            stream.write("\n")
    for change in plan.changes:
        destination = f" -> {change.destination_path}" if change.destination_path is not None else ""
        write_line(stream, f"Affected path: {change.path}{destination}")
    for directory in plan.created_directories:
        write_line(stream, f"Derived effect: create directory {directory.path}")
    write_line(stream, f"Plan digest: {plan.plan_digest}")


def _command_text(command: PlannedCommand) -> str:
    request = command.request
    if request.mode is CommandExecutionMode.ARGV:
        if request.argv is not None:
            return bound_text(" ".join(request.argv))
    elif request.shell is not None:
        return bound_text(request.shell)
    msg = "planned command omitted the request content required by its execution mode"
    raise ValueError(msg)
