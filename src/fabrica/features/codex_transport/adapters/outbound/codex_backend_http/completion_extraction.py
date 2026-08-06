"""Extract completion text and usage facts from Codex response payloads."""

import json
from collections.abc import Mapping, Sequence
from typing import cast

from fabrica.features.codex_transport.adapters.outbound.codex_backend_http.response_helpers import bounded
from fabrica.features.codex_transport.application.usage_mapping import CodexCompletionUsageFacts
from fabrica.shared_kernel.model_usage import ModelUsageEvidenceSource


def extract_output_text(json_body: object) -> str | None:
    """Extract completion text from JSON or stream-backed Codex response shapes."""
    if isinstance(json_body, str):
        return _extract_output_text_from_event_stream(json_body)
    if not isinstance(json_body, Mapping):
        return None
    return _extract_output_text_from_mapping(cast("Mapping[object, object]", json_body))


def extract_completion_usage_facts(json_body: object) -> CodexCompletionUsageFacts | None:
    """Extract safe token usage facts from JSON or stream-backed response shapes."""
    if isinstance(json_body, str):
        return _extract_completion_usage_facts_from_event_stream(json_body)
    if not isinstance(json_body, Mapping):
        return None
    return _extract_completion_usage_facts_from_mapping(
        cast("Mapping[object, object]", json_body),
        source=ModelUsageEvidenceSource.RESPONSE_PAYLOAD,
    )


def _extract_completion_usage_facts_from_event_stream(response_text: str) -> CodexCompletionUsageFacts | None:
    latest_facts: CodexCompletionUsageFacts | None = None
    for payload in _iter_event_payloads(response_text):
        facts = _extract_completion_usage_facts_from_mapping(payload, source=ModelUsageEvidenceSource.STREAM_EVENT)
        if facts is not None:
            latest_facts = facts
    return latest_facts


def _extract_completion_usage_facts_from_mapping(
    json_body: Mapping[object, object],
    *,
    source: ModelUsageEvidenceSource,
) -> CodexCompletionUsageFacts | None:
    usage = _usage_mapping_from_response_shape(json_body)
    candidate = usage if usage is not None else json_body
    details = _first_mapping(candidate.get("input_token_details"), candidate.get("prompt_tokens_details"))
    output_details = _first_mapping(candidate.get("output_token_details"), candidate.get("completion_tokens_details"))
    facts = CodexCompletionUsageFacts(
        source=source,
        input_tokens=_optional_non_negative_int(candidate.get("input_tokens"), candidate.get("prompt_tokens")),
        output_tokens=_optional_non_negative_int(candidate.get("output_tokens"), candidate.get("completion_tokens")),
        total_tokens=_optional_non_negative_int(candidate.get("total_tokens")),
        cached_input_tokens=_optional_non_negative_int(
            candidate.get("cached_input_tokens"),
            details.get("cached_tokens") if details is not None else None,
        ),
        reasoning_tokens=_optional_non_negative_int(
            candidate.get("reasoning_tokens"),
            output_details.get("reasoning_tokens") if output_details is not None else None,
        ),
        model=_safe_model(candidate.get("model"), json_body.get("model")),
    )
    return facts if facts.has_token_counts else None


def _extract_output_text_from_mapping(json_body: Mapping[object, object]) -> str | None:
    direct_output = json_body.get("output_text")
    if isinstance(direct_output, str) and direct_output:
        return direct_output
    content_output = _extract_output_text_from_content(json_body.get("content"))
    if content_output is not None:
        return content_output
    nested_output = _extract_output_text_from_nested_mapping(json_body)
    if nested_output is not None:
        return nested_output
    output = json_body.get("output")
    if not isinstance(output, Sequence) or isinstance(output, str | bytes):
        return None
    return _extract_output_text_from_output_items(output)


def _extract_output_text_from_event_stream(response_text: str) -> str | None:
    extracted_parts: list[str] = []
    done_text: str | None = None
    for payload in _iter_event_payloads(response_text):
        event_type = payload.get("type")
        text = payload.get("text")
        delta = payload.get("delta")
        if event_type == "response.output_text.done" and isinstance(text, str):
            done_text = text
            continue
        if event_type == "response.output_text.delta" and isinstance(delta, str):
            extracted_parts.append(delta)
            continue
        output_text = extract_output_text(payload)
        if output_text is not None and not extracted_parts:
            extracted_parts.append(output_text)
    if not extracted_parts:
        return done_text
    return "".join(extracted_parts)


def _iter_event_payloads(response_text: str) -> tuple[Mapping[object, object], ...]:
    payloads: list[Mapping[object, object]] = []
    for line in response_text.splitlines():
        if not line.startswith("data:"):
            continue
        event_data = line.removeprefix("data:").strip()
        if event_data in {"", "[DONE]"}:
            continue
        try:
            payload = json.loads(event_data)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, Mapping):
            payloads.append(cast("Mapping[object, object]", payload))
    return tuple(payloads)


def _extract_output_text_from_content(content: object) -> str | None:
    extracted_parts: list[str] = []
    _append_content_texts(extracted_parts=extracted_parts, content=content)
    return "".join(extracted_parts) if extracted_parts else None


def _extract_output_text_from_nested_mapping(json_body: Mapping[object, object]) -> str | None:
    for nested_key in ("response", "item", "part"):
        nested_output = json_body.get(nested_key)
        if isinstance(nested_output, Mapping):
            extracted_output = _extract_output_text_from_mapping(cast("Mapping[object, object]", nested_output))
            if extracted_output is not None:
                return extracted_output
    return None


def _extract_output_text_from_output_items(output: Sequence[object]) -> str | None:
    extracted_parts: list[str] = []
    for output_item in output:
        if isinstance(output_item, Mapping):
            _append_content_texts(extracted_parts=extracted_parts, content=output_item.get("content"))
    return "".join(extracted_parts) if extracted_parts else None


def _append_content_texts(*, extracted_parts: list[str], content: object) -> None:
    if not isinstance(content, Sequence) or isinstance(content, str | bytes):
        return
    for content_item in content:
        if not isinstance(content_item, Mapping):
            continue
        text = content_item.get("text")
        if isinstance(text, str):
            extracted_parts.append(text)


def _usage_mapping_from_response_shape(json_body: Mapping[object, object]) -> Mapping[object, object] | None:
    usage = _first_mapping(json_body.get("usage"))
    if usage is not None:
        return usage
    for nested_key in ("response", "item", "part"):
        nested_value = json_body.get(nested_key)
        if isinstance(nested_value, Mapping):
            nested_usage = _usage_mapping_from_response_shape(cast("Mapping[object, object]", nested_value))
            if nested_usage is not None:
                return nested_usage
    return None


def _first_mapping(*values: object) -> Mapping[object, object] | None:
    for value in values:
        if isinstance(value, Mapping):
            return cast("Mapping[object, object]", value)
    return None


def _optional_non_negative_int(*values: object) -> int | None:
    for value in values:
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
    return None


def _safe_model(*values: object) -> str | None:
    for value in values:
        if isinstance(value, str) and value:
            return bounded(value, 120)
    return None
