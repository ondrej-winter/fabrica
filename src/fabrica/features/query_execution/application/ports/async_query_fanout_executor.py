"""Application-owned port for bounded async query fan-out."""

from collections.abc import Awaitable, Callable, Sequence
from typing import Protocol, TypeVar

T = TypeVar("T")


class AsyncQueryFanoutExecutor(Protocol):
    """Fan out independent async query operations with deterministic ordering.

    Synchronous workflow facades should wrap their higher-level async use cases
    instead of adding a sync API to this event-loop-dependent primitive.
    """

    async def gather_ordered(
        self,
        operations: Sequence[Callable[[], Awaitable[T]]],
        *,
        max_concurrency: int,
    ) -> tuple[T, ...]:
        """Await operations with bounded concurrency and return results in input order."""
        ...
