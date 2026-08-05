"""Tests for bounded async query execution."""

import asyncio

import pytest

from fabrica.features.query_execution.application.use_cases import BoundedAsyncQueryExecutor


def test_gather_ordered_preserves_input_order_when_operations_finish_out_of_order() -> None:
    events: list[str] = []

    async def first() -> str:
        events.append("start:first")
        await asyncio.sleep(0.02)
        events.append("finish:first")
        return "first"

    async def second() -> str:
        events.append("start:second")
        await asyncio.sleep(0)
        events.append("finish:second")
        return "second"

    result = asyncio.run(BoundedAsyncQueryExecutor().gather_ordered((first, second), max_concurrency=2))

    assert result == ("first", "second")
    assert events == ["start:first", "start:second", "finish:second", "finish:first"]


def test_gather_ordered_respects_max_concurrency() -> None:
    active_count = 0
    max_seen_active_count = 0

    async def operation() -> str:
        nonlocal active_count, max_seen_active_count
        active_count += 1
        max_seen_active_count = max(max_seen_active_count, active_count)
        await asyncio.sleep(0)
        active_count -= 1
        return "ok"

    result = asyncio.run(
        BoundedAsyncQueryExecutor().gather_ordered((operation, operation, operation), max_concurrency=1),
    )

    assert result == ("ok", "ok", "ok")
    assert max_seen_active_count == 1


def test_gather_ordered_fails_closed_when_any_operation_fails() -> None:
    async def failing() -> str:
        msg = "query failed"
        raise RuntimeError(msg)

    with pytest.raises(RuntimeError, match="query failed"):
        asyncio.run(BoundedAsyncQueryExecutor().gather_ordered((failing,), max_concurrency=1))


def test_gather_ordered_rejects_non_positive_concurrency() -> None:
    with pytest.raises(ValueError, match="max_concurrency"):
        asyncio.run(BoundedAsyncQueryExecutor().gather_ordered((), max_concurrency=0))
