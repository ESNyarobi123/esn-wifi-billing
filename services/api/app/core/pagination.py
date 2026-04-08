from __future__ import annotations

from math import ceil
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession


class PaginationParams(BaseModel):
    page: int = Field(1, ge=1)
    per_page: int = Field(20, ge=1, le=200)
    sort: str | None = None


async def paginate(
    session: AsyncSession,
    stmt: Select[Any],
    *,
    count_stmt: Select[Any] | None = None,
    page: int,
    per_page: int,
) -> tuple[list[Any], int]:
    if count_stmt is None:
        sub = stmt.order_by(None).subquery()
        count_stmt = select(func.count()).select_from(sub)
    total = int((await session.execute(count_stmt)).scalar_one())
    offset = (page - 1) * per_page
    rows = (await session.execute(stmt.offset(offset).limit(per_page))).scalars().all()
    return list(rows), total


def total_pages(total: int, per_page: int) -> int:
    if per_page <= 0:
        return 0
    return max(1, ceil(total / per_page))
