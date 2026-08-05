"""Bounded async query execution primitives."""

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from typing import TypeVar, cast

T = TypeVar("T")


class BoundedAsyncQueryExecutor:
    """Run independent async query operations with bounded fan-out."""

    async def gather_ordered(
        self,
        operations: Sequence[Callable[[], Awaitable[T]]],
        *,
        max_concurrency: int,
    ) -> tuple[T, ...]:
        """Run operations concurrently while preserving input order in the result."""
        if max_concurrency < 1:
            msg = "max_concurrency must be at least 1"
            raise ValueError(msg)

        semaphore = asyncio.Semaphore(max_concurrency)
        results: list[T | None] = [None] * len(operations)

        async def run_one(index: int, operation: Callable[[], Awaitable[T]]) -> None:
            async with semaphore:
                results[index] = await operation()

        try:
            async with asyncio.TaskGroup() as task_group:
                for index, operation in enumerate(operations):
                    task_group.create_task(run_one(index, operation))
        except ExceptionGroup as err:
            if len(err.exceptions) == 1:
                raise err.exceptions[0] from err
            raise

        return tuple(cast("T", result) for result in results)
