"""Application-owned ports for reusable async query fan-out."""

from fabrica.features.query_execution.application.ports.async_query_fanout_executor import (
    AsyncQueryFanoutExecutor,
)

__all__ = ["AsyncQueryFanoutExecutor"]
