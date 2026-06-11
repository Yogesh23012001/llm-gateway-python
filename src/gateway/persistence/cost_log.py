"""Postgres cost tracking — implemented in Hour 4."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class CostRecord:
    request_id: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float


class CostLog:
    """Persists per-request token usage and computed cost to Postgres."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        # Hour 4: create the asyncpg pool / SQLAlchemy async engine.

    async def record(self, record: CostRecord) -> None:
        raise NotImplementedError("Cost logging is implemented in Hour 4.")
