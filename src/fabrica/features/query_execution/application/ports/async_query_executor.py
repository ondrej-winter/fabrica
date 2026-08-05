"""Application-owned port for bounded async query fan-out."""

from collections.abc import Awaitable, Callable, Sequence
from typing import Protocol, TypeVar

T = TypeVar("T")


class AsyncQueryExecutor(Protocol):
    """Execute independent async query operations with deterministic ordering."""

    async def gather_ordered(
        self,
        operations: Sequence[Callable[[], Awaitable[T]]],
        *,
        max_concurrency: int,
    ) -> tuple[T, ...]:
        """Run operations with bounded concurrency and return results in input order."""
        ...
