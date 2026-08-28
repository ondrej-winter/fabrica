"""Composition helpers for explicitly authorized workspace-reading tools."""

from pathlib import Path

from fabrica.features.agent_runtime.application.ports import AsyncRegisteredTool
from fabrica.features.workspace_reading.adapters.inbound.registered_tool import create_read_files_registered_tool
from fabrica.features.workspace_reading.adapters.outbound.posix_filesystem import PosixHelperProcessFileReader
from fabrica.features.workspace_reading.application.dtos import ReadFilesLimits
from fabrica.features.workspace_reading.application.use_cases import ReadFiles


def create_read_files_registered_tool_adapter(
    workspace_root: Path,
    *,
    external_read_authorized: bool,
    image_input_supported: bool,
    limits: ReadFilesLimits | None = None,
) -> AsyncRegisteredTool:
    """Create the model-facing read-files tool from explicit host-owned policy.

    Construction only wires immutable configuration and adapters. It does not
    inspect the workspace, start helper processes, or call a model provider.
    """
    resolved_limits = limits or ReadFilesLimits()
    use_case = ReadFiles(file_reader=PosixHelperProcessFileReader(workspace_root=workspace_root))
    return create_read_files_registered_tool(
        use_case,
        limits=resolved_limits,
        external_read_authorized=external_read_authorized,
        image_input_supported=image_input_supported,
    )


__all__ = ["create_read_files_registered_tool_adapter"]
