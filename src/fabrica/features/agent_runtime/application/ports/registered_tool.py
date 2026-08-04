"""Registered in-process tool contracts for local agent runtimes."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from fabrica.features.agent_runtime.application.dtos import SafeRuntimeMetadataValue, ToolDefinition

RegisteredToolHandler = Callable[[Mapping[str, SafeRuntimeMetadataValue]], str]


@dataclass(frozen=True, slots=True)
class RegisteredTool:
    """Explicitly registered in-process callable and application tool definition."""

    definition: ToolDefinition
    handler: RegisteredToolHandler
