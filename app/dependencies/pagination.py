from fastapi import Query
from pydantic import BaseModel, field_validator


DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100


class PaginationParams(BaseModel):
    page: int = 1
    per_page: int = DEFAULT_PER_PAGE

    @field_validator("page")
    @classmethod
    def v_page(cls, v: int) -> int:
        return max(1, v)

    @field_validator("per_page")
    @classmethod
    def v_per_page(cls, v: int) -> int:
        v = v or DEFAULT_PER_PAGE
        return min(MAX_PER_PAGE, max(1, v))


async def get_pagination(
    page: int = Query(1, ge=1),
    per_page: int = Query(DEFAULT_PER_PAGE, ge=1, le=MAX_PER_PAGE),
) -> PaginationParams:
    return PaginationParams(page=page, per_page=per_page)
