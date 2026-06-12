"""Persist every completion to Postgres for cost tracking and audit.

One row per completion: request_id, model, provider, tokens, cost, latency,
outcome. This is the data behind 'which model/provider/period cost what'.
"""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
import structlog
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

logger = structlog.get_logger(__name__)

metadata = sa.MetaData()

completions_table = sa.Table(
    "completions",
    metadata,
    sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
    sa.Column("request_id", sa.String(64), nullable=False, index=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("requested_model", sa.String(128), nullable=False),
    sa.Column("resolved_model", sa.String(128), nullable=False),
    sa.Column("provider", sa.String(32), nullable=False, index=True),
    sa.Column("prompt_tokens", sa.Integer, nullable=False),
    sa.Column("completion_tokens", sa.Integer, nullable=False),
    sa.Column("total_tokens", sa.Integer, nullable=False),
    sa.Column("cost_usd", sa.Numeric(12, 8), nullable=False),
    sa.Column("latency_ms", sa.Float, nullable=False),
    sa.Column("outcome", sa.String(32), nullable=False),  # "success" | "error"
)


async def init_db(engine: AsyncEngine) -> None:
    """Create tables if they don't exist. (For prod, use Alembic migrations.)"""
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)


async def record_completion(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    request_id: str,
    requested_model: str,
    resolved_model: str,
    provider: str,
    prompt_tokens: int,
    completion_tokens: int,
    cost_usd: float,
    latency_ms: float,
    outcome: str,
) -> None:
    """Best-effort write. A logging failure must never fail the request."""
    try:
        async with session_factory() as session:
            await session.execute(
                sa.insert(completions_table).values(
                    request_id=request_id,
                    created_at=datetime.now(UTC),
                    requested_model=requested_model,
                    resolved_model=resolved_model,
                    provider=provider,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                    cost_usd=cost_usd,
                    latency_ms=latency_ms,
                    outcome=outcome,
                )
            )
            await session.commit()
    except Exception:
        # Cost logging is best-effort. Log the failure, never propagate.
        logger.exception("cost_log_write_failed", request_id=request_id)