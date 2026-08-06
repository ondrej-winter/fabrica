"""Map Codex backend HTTP outcomes to application result contracts."""

from fabrica.features.codex_transport.adapters.outbound.codex_backend_http.completion_extraction import (
    extract_completion_usage_facts,
    extract_output_text,
)
from fabrica.features.codex_transport.adapters.outbound.codex_backend_http.response_helpers import (
    AUTHENTICATION_STATUS_CODES,
    MAX_ERROR_TYPE_LENGTH,
    RATE_LIMIT_STATUS_CODE,
    body_contains_token,
    bounded,
    extract_error_type,
    has_rate_limit_signal,
    is_edge_challenge_response,
    is_success_status_code,
    response_shape,
)
from fabrica.features.codex_transport.adapters.outbound.codex_backend_http.response_types import (
    CodexBackendResponse,
    CodexUsageResponse,
)
from fabrica.features.codex_transport.adapters.outbound.codex_backend_http.usage_extraction import (
    extract_usage_evidence,
)
from fabrica.features.codex_transport.application.dtos import (
    CodexTransportObservation,
    CodexTransportResult,
    CodexTransportStatus,
    CodexUsageEvidence,
    CodexUsageResult,
)
from fabrica.features.codex_transport.application.usage_mapping import (
    CodexCompletionUsageFacts,
    map_codex_completion_evidence,
)


def map_codex_backend_response(response: CodexBackendResponse) -> CodexTransportResult:
    """Map a completion response into the normalized application result contract."""
    if is_edge_challenge_response(response.headers):
        return _completion_result(
            status=CodexTransportStatus.TRANSPORT_ERROR,
            response=response,
            outcome=("Codex backend request was blocked by edge challenge mitigation", "edge_challenge"),
        )
    if response.status_code in AUTHENTICATION_STATUS_CODES:
        return _completion_result(
            status=CodexTransportStatus.AUTHENTICATION_FAILED,
            response=response,
            outcome=("Codex backend rejected credentials", "authentication"),
        )
    if _is_completion_quota_exceeded_response(response):
        return _completion_result(
            status=CodexTransportStatus.QUOTA_EXCEEDED,
            response=response,
            outcome=("Codex backend quota was exceeded", "quota"),
        )
    if response.status_code == RATE_LIMIT_STATUS_CODE or has_rate_limit_signal(response.headers):
        return _completion_result(
            status=CodexTransportStatus.RATE_LIMITED,
            response=response,
            outcome=("Codex backend request was rate limited", "rate_limit"),
        )
    if is_success_status_code(response.status_code):
        return _map_success_response(response)
    return _completion_result(
        status=CodexTransportStatus.TRANSPORT_ERROR,
        response=response,
        outcome=("Codex backend returned an unsuccessful response", "backend_error"),
    )


def map_codex_backend_transport_error(err: BaseException) -> CodexTransportResult:
    """Map a client/network exception into a secret-safe transport error result."""
    return CodexTransportResult(
        status=CodexTransportStatus.TRANSPORT_ERROR,
        observations=(
            CodexTransportObservation(
                message="Codex backend request failed before a response was received",
                metadata={"category": "client_error", "error_type": bounded(type(err).__name__, MAX_ERROR_TYPE_LENGTH)},
            ),
        ),
    )


def map_codex_usage_response(response: CodexUsageResponse) -> CodexUsageResult:
    """Map a usage response into safe status and allowlisted usage evidence."""
    if is_edge_challenge_response(response.headers):
        return _usage_result(
            status=CodexTransportStatus.TRANSPORT_ERROR,
            message="Codex usage request was blocked by edge challenge mitigation",
            response=response,
            category="edge_challenge",
        )
    if response.status_code in AUTHENTICATION_STATUS_CODES:
        return _usage_result(
            status=CodexTransportStatus.AUTHENTICATION_FAILED,
            message="Codex usage endpoint rejected credentials",
            response=response,
            category="authentication",
        )
    if _is_usage_quota_exceeded_response(response):
        return _usage_result(
            status=CodexTransportStatus.QUOTA_EXCEEDED,
            message="Codex usage endpoint reported quota exhaustion",
            response=response,
            category="quota",
        )
    if response.status_code == RATE_LIMIT_STATUS_CODE or has_rate_limit_signal(response.headers):
        return _usage_result(
            status=CodexTransportStatus.RATE_LIMITED,
            message="Codex usage endpoint was rate limited",
            response=response,
            category="rate_limit",
        )
    if is_success_status_code(response.status_code):
        return _map_usage_success_response(response)
    return _usage_result(
        status=CodexTransportStatus.TRANSPORT_ERROR,
        message="Codex usage endpoint returned an unsuccessful response",
        response=response,
        category="backend_error",
    )


def map_codex_usage_transport_error(err: BaseException) -> CodexUsageResult:
    """Map a usage client/network exception into a secret-safe result."""
    return CodexUsageResult(
        status=CodexTransportStatus.TRANSPORT_ERROR,
        observations=(
            CodexTransportObservation(
                message="Codex usage request failed before a response was received",
                metadata={"category": "client_error", "error_type": bounded(type(err).__name__, MAX_ERROR_TYPE_LENGTH)},
            ),
        ),
    )


def _map_success_response(response: CodexBackendResponse) -> CodexTransportResult:
    output_text = extract_output_text(response.json_body)
    if output_text is None:
        return _completion_result(
            status=CodexTransportStatus.BACKEND_SHAPE_MISMATCH,
            response=response,
            outcome=("Codex backend response shape was unexpected", "shape_mismatch"),
        )
    return _completion_result(
        status=CodexTransportStatus.SUCCESS,
        response=response,
        outcome=("Codex backend returned expected response shape", "success"),
        output_text=output_text,
        usage_facts=extract_completion_usage_facts(response.json_body),
    )


def _completion_result(
    *,
    status: CodexTransportStatus,
    response: CodexBackendResponse,
    outcome: tuple[str, str],
    output_text: str | None = None,
    usage_facts: CodexCompletionUsageFacts | None = None,
) -> CodexTransportResult:
    message, category = outcome
    generic_evidence = map_codex_completion_evidence(status=status, usage_facts=usage_facts)
    return CodexTransportResult(
        status=status,
        output_text=output_text,
        observations=(_response_observation(message=message, category=category, response=response),),
        usage_evidence=generic_evidence.usage_evidence,
        cost_evidence=generic_evidence.cost_evidence,
    )


def _map_usage_success_response(response: CodexUsageResponse) -> CodexUsageResult:
    evidence_values = extract_usage_evidence(response.json_body, response.headers)
    if not evidence_values:
        return _usage_result(
            status=CodexTransportStatus.BACKEND_SHAPE_MISMATCH,
            message="Codex usage response shape was unexpected",
            response=response,
            category="shape_mismatch",
        )
    return _usage_result(
        status=CodexTransportStatus.SUCCESS,
        message="Codex usage evidence was retrieved",
        response=response,
        category="success",
        evidence=CodexUsageEvidence(evidence_values),
    )


def _usage_result(
    *,
    status: CodexTransportStatus,
    message: str,
    response: CodexUsageResponse,
    category: str,
    evidence: CodexUsageEvidence | None = None,
) -> CodexUsageResult:
    return CodexUsageResult(
        status=status,
        evidence=evidence,
        observations=(_response_observation(message=message, category=category, response=response),),
    )


def _response_observation(
    *,
    message: str,
    category: str,
    response: CodexBackendResponse | CodexUsageResponse,
) -> CodexTransportObservation:
    return CodexTransportObservation(
        message=message,
        metadata={
            "http_status": response.status_code,
            "category": category,
            "header_count": len(response.headers),
            "response_shape": response_shape(response.json_body),
            "error_type": extract_error_type(response.json_body),
        },
    )


def _is_completion_quota_exceeded_response(response: CodexBackendResponse) -> bool:
    return response.status_code == RATE_LIMIT_STATUS_CODE and body_contains_token(response.json_body, "quota")


def _is_usage_quota_exceeded_response(response: CodexUsageResponse) -> bool:
    return response.status_code == RATE_LIMIT_STATUS_CODE and body_contains_token(response.json_body, "quota")
