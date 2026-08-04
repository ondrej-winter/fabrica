"""Explicit in-process tool registry adapter for bounded tool-loop proofs."""

from collections.abc import Mapping
from dataclasses import dataclass

from fabrica.features.agent_runtime.application.dtos import (
    MAX_TOOL_RESPONSE_TEXT_CHARS,
    RuntimeObservation,
    SafeRuntimeMetadataValue,
    SelectedSkillToolDeclaration,
    SkillToolExposureStatus,
    SkillToolPreparationCommand,
    SkillToolPreparationResult,
    ToolCallRequest,
    ToolCallResult,
    ToolCallResultStatus,
    ToolDefinition,
    ToolLoopLimits,
)
from fabrica.features.agent_runtime.application.ports import RegisteredTool

_UNKNOWN_TOOL_MESSAGE = "requested tool is not registered"
_INVALID_ARGUMENTS_MESSAGE = "registered tool rejected arguments"
_TOOL_FAILURE_MESSAGE = "registered tool execution failed"
_TOOL_TIMEOUT_MESSAGE = "registered tool execution timed out"
_TOOL_LIMIT_MESSAGE = "registered tool result exceeded output limit"


@dataclass(frozen=True, slots=True)
class SkillAssociatedRegisteredTool:
    """Explicit in-process tool registration associated with a selected skill."""

    skill_id: str
    registered_tool: RegisteredTool
    label: str | None = None
    metadata: Mapping[str, SafeRuntimeMetadataValue] | None = None

    def to_declaration(self) -> SelectedSkillToolDeclaration:
        """Return an application-safe declaration without exposing the callable."""
        return SelectedSkillToolDeclaration(
            skill_id=self.skill_id,
            status=SkillToolExposureStatus.REGISTERED,
            tool=self.registered_tool.definition,
            label=self.label,
            metadata=self.metadata or {},
        )


class RegisteredSkillToolPreparer:
    """Prepare explicitly supplied skill-associated registered tools.

    This adapter does not inspect Agent Skill files, discover tools, dynamically
    import callables, execute scripts, spawn subprocesses, or call backends. It
    only maps composition-supplied registrations into application declarations.
    """

    def __init__(self, tools: tuple[SkillAssociatedRegisteredTool, ...] = ()) -> None:
        self._tools = tuple(tools)

    def prepare(self, command: SkillToolPreparationCommand) -> SkillToolPreparationResult:
        """Prepare application declarations for explicit skill tool registrations."""
        del command
        return SkillToolPreparationResult(
            declarations=tuple(tool.to_declaration() for tool in self._tools),
        )


class RegisteredToolExecutor:
    """Execute explicitly registered deterministic in-process tools.

    This adapter is intentionally narrow: tools are supplied directly by
    composition or tests. It does not discover tools, dynamically import callables,
    inspect Agent Skills, execute scripts, spawn subprocesses, or call shells.
    """

    def __init__(self, tools: tuple[RegisteredTool, ...] = ()) -> None:
        tool_names = [tool.definition.name for tool in tools]
        if len(set(tool_names)) != len(tool_names):
            msg = "registered tool names must be unique"
            raise ValueError(msg)
        self._tools = {tool.definition.name: tool for tool in tools}

    @property
    def tool_definitions(self) -> tuple[ToolDefinition, ...]:
        """Return application-safe definitions for registered tools."""
        return tuple(tool.definition for tool in self._tools.values())

    def execute_tool(self, request: ToolCallRequest, limits: ToolLoopLimits) -> ToolCallResult:
        """Execute one explicitly registered tool request."""
        tool = self._tools.get(request.tool_name)
        if tool is None:
            return _failure_result(
                request,
                ToolCallResultStatus.UNKNOWN_TOOL,
                _UNKNOWN_TOOL_MESSAGE,
                category="unknown_tool",
            )

        try:
            result_text = tool.handler(request.arguments)
        except (KeyError, TypeError, ValueError):
            return _failure_result(
                request,
                ToolCallResultStatus.INVALID_ARGUMENTS,
                _INVALID_ARGUMENTS_MESSAGE,
                category="invalid_arguments",
            )
        except TimeoutError:
            return _failure_result(
                request,
                ToolCallResultStatus.TIMEOUT,
                _TOOL_TIMEOUT_MESSAGE,
                category="timeout",
            )
        except (OSError, RuntimeError):
            return _failure_result(
                request,
                ToolCallResultStatus.TOOL_FAILURE,
                _TOOL_FAILURE_MESSAGE,
                category="tool_failure",
            )

        return _success_result(request, result_text, limits)


def _success_result(request: ToolCallRequest, result_text: str, limits: ToolLoopLimits) -> ToolCallResult:
    max_chars = min(limits.max_tool_result_chars, MAX_TOOL_RESPONSE_TEXT_CHARS)
    if len(result_text) <= max_chars:
        return ToolCallResult(
            call_id=request.call_id,
            tool_name=request.tool_name,
            status=ToolCallResultStatus.SUCCESS,
            result_text=result_text,
        )
    return ToolCallResult(
        call_id=request.call_id,
        tool_name=request.tool_name,
        status=ToolCallResultStatus.LIMIT_EXCEEDED,
        result_text=result_text[:max_chars],
        error_message=_TOOL_LIMIT_MESSAGE,
        observations=(
            RuntimeObservation(
                message="registered tool result text was truncated",
                metadata={"tool_name": request.tool_name, "max_chars": max_chars},
            ),
        ),
    )


def _failure_result(
    request: ToolCallRequest,
    status: ToolCallResultStatus,
    error_message: str,
    *,
    category: str,
) -> ToolCallResult:
    return ToolCallResult(
        call_id=request.call_id,
        tool_name=request.tool_name,
        status=status,
        error_message=error_message,
        observations=(
            RuntimeObservation(
                message=error_message,
                metadata={"tool_name": request.tool_name, "category": category},
            ),
        ),
    )
