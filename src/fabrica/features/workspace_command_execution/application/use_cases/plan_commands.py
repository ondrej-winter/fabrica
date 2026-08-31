"""Command planning behind explicit host-policy boundaries."""

from dataclasses import dataclass

from fabrica.features.workspace_command_execution.application.dtos import (
    DEFAULT_MAX_COMMAND_PREVIEW_CHARS,
    CommandError,
    CommandErrorCode,
    CommandExecutionStatus,
    CommandRequest,
    CommandResult,
    PlannedCommand,
    RunCommandsCommand,
)
from fabrica.features.workspace_command_execution.application.errors import CommandPlanningError
from fabrica.features.workspace_command_execution.application.ports import (
    CommandApprovalResolver,
    CommandEnvironmentBuilder,
    CommandPermissionDecision,
    CommandPermissionEvaluator,
    CommandSandboxPreflight,
    CommandWorkspaceResolver,
)


@dataclass(frozen=True, slots=True)
class PlanCommands:
    """Prepare commands for supervision while enforcing host-owned admission policy."""

    workspace_resolver: CommandWorkspaceResolver
    environment_builder: CommandEnvironmentBuilder
    permission_evaluator: CommandPermissionEvaluator
    approval_resolver: CommandApprovalResolver
    sandbox_preflight: CommandSandboxPreflight

    async def plan(self, command: RunCommandsCommand) -> tuple[PlannedCommand | CommandResult, ...]:
        """Plan each command independently, preserving order after planning failures."""
        entries: list[PlannedCommand | CommandResult] = []
        for index, request in enumerate(command.commands):
            entries.append(await self._plan_one(index, request))
        return tuple(entries)

    async def _plan_one(self, index: int, request: CommandRequest) -> PlannedCommand | CommandResult:
        preview = _command_preview(request)
        try:
            planned = PlannedCommand(
                index=index,
                request=request,
                resolved_cwd=self.workspace_resolver.resolve_cwd(request.cwd),
                environment=self.environment_builder.build_environment(dict(request.env)),
            )
            decision = await self.permission_evaluator.evaluate(planned)
            if decision is CommandPermissionDecision.DENY:
                return _rejected(index, preview, CommandErrorCode.PERMISSION_DENIED, "command permission was denied")
            if decision is CommandPermissionDecision.REQUIRE_APPROVAL and not await self.approval_resolver.resolve(
                planned
            ):
                return _rejected(index, preview, CommandErrorCode.PERMISSION_DENIED, "command approval was not granted")
            if not await self.sandbox_preflight.allow(planned):
                return _rejected(
                    index, preview, CommandErrorCode.SANDBOX_DENIED, "command sandbox admission was denied"
                )
        except CommandPlanningError as err:
            return _rejected(index, preview, err.code, err.message)
        except (OSError, ValueError, TypeError):
            return _rejected(index, preview, CommandErrorCode.INTERNAL_EXECUTION_ERROR, "command planning failed")
        else:
            return planned


def _command_preview(request: CommandRequest) -> str:
    """Return the bounded, model-visible representation of one requested command."""
    text = request.shell if request.shell is not None else " ".join(request.argv or ())
    return text[:DEFAULT_MAX_COMMAND_PREVIEW_CHARS]


def _rejected(index: int, preview: str, code: CommandErrorCode, message: str) -> CommandResult:
    """Create a command-scoped outcome for a failed pre-execution check."""
    return CommandResult(
        index=index,
        command_preview=preview,
        status=CommandExecutionStatus.SPAWN_FAILED,
        duration_ms=0,
        error=CommandError(code=code, message=message),
    )
