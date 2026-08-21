"""Composition helpers for Codex-backed and PydanticAI-shaped runtimes."""

from pathlib import Path

from fabrica.adapters.outbound.httpx_client import HttpTimeout, HttpxRetryClient
from fabrica.features.agent_runtime.adapters.outbound.codex_transport_model import CodexTransportAgentModel
from fabrica.features.agent_runtime.adapters.outbound.pydantic_ai_model import (
    CodexTransportPydanticAICompletion,
    PydanticAIAgentModel,
    PydanticAICompletion,
)
from fabrica.features.agent_runtime.application.use_cases import RunLocalAgent
from fabrica.features.codex_transport.adapters.outbound.codex_auth_file import CodexAuthFileCredentialStore
from fabrica.features.codex_transport.adapters.outbound.codex_backend_http import (
    CodexBackendHttpAdapter,
    CodexBackendRequestSettings,
    CodexUsageRequestSettings,
)
from fabrica.features.codex_transport.application.use_cases import CompleteWithCodexTransport

DEFAULT_CODEX_AUTH_FILE = Path.home() / ".codex" / "auth.json"
DEFAULT_COMMIT_MESSAGE_CODEX_MODEL = "gpt-5.3-codex-spark"
DEFAULT_COMMIT_MESSAGE_CODEX_REASONING_EFFORT = "low"


def create_codex_runtime(
    *,
    auth_file_path: Path | None = None,
    http_client: HttpxRetryClient | None = None,
    timeout: float | HttpTimeout | None = None,
    request_settings: CodexBackendRequestSettings | None = None,
    usage_request_settings: CodexUsageRequestSettings | None = None,
) -> RunLocalAgent:
    """Create a local runtime use case backed by the Codex transport path.

    The factory wires concrete adapters at the composition root but does not read
    credentials or call the live backend during construction. Credential loading
    and HTTP I/O happen only when the returned runtime use case is executed.
    """
    if timeout is not None:
        backend = CodexBackendHttpAdapter(
            request_settings=request_settings,
            usage_request_settings=usage_request_settings,
            completion_timeout=timeout,
            usage_timeout=timeout,
            http_client=http_client or HttpxRetryClient(),
        )
    else:
        backend = CodexBackendHttpAdapter(
            request_settings=request_settings,
            usage_request_settings=usage_request_settings,
            http_client=http_client or HttpxRetryClient(),
        )

    transport = CompleteWithCodexTransport(
        credential_store=CodexAuthFileCredentialStore(auth_file_path or DEFAULT_CODEX_AUTH_FILE),
        backend=backend,
    )
    return RunLocalAgent(model=CodexTransportAgentModel(transport=transport))


def create_pydantic_ai_runtime(
    *,
    completion: PydanticAICompletion,
    model_name: str = "synthetic-codex",
) -> RunLocalAgent:
    """Create a local runtime use case backed by the PydanticAI adapter proof.

    The factory wires an explicitly supplied completion dependency for offline
    compatibility tests and future composition experiments. Construction does
    not read credentials, call a backend, load skill roots, or execute scripts.
    """
    return RunLocalAgent(model=PydanticAIAgentModel(completion=completion, model_name=model_name))


def create_codex_pydantic_ai_runtime(
    *,
    auth_file_path: Path | None = None,
    http_client: HttpxRetryClient | None = None,
    timeout: float | HttpTimeout | None = None,
    request_settings: CodexBackendRequestSettings | None = None,
    model_name: str = "codex-transport",
) -> RunLocalAgent:
    """Create a PydanticAI runtime backed by the Codex completion boundary.

    Construction only wires dependencies. Credential loading and HTTP I/O happen
    when the returned runtime is executed.
    """
    if timeout is not None:
        backend = CodexBackendHttpAdapter(
            request_settings=request_settings,
            completion_timeout=timeout,
            http_client=http_client or HttpxRetryClient(),
        )
    else:
        backend = CodexBackendHttpAdapter(
            request_settings=request_settings,
            http_client=http_client or HttpxRetryClient(),
        )
    transport = CompleteWithCodexTransport(
        credential_store=CodexAuthFileCredentialStore(auth_file_path or DEFAULT_CODEX_AUTH_FILE),
        backend=backend,
    )
    completion = CodexTransportPydanticAICompletion(transport=transport)
    return RunLocalAgent(model=PydanticAIAgentModel(completion=completion, model_name=model_name))
