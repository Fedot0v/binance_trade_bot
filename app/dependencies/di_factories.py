from typing import TypeVar, Type

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.db_dependencie import get_session


S = TypeVar("S")
T = TypeVar("T")


def get_repository(repo_class: Type[T]):
    def _get_repo(db: AsyncSession = Depends(get_session)) -> T:
        return repo_class(db)
    return _get_repo


def get_service(service_class: Type[S], repo_class: Type[T]):
    repo_dependency = get_repository(repo_class)

    def _get_service(
        repo: T = Depends(repo_dependency)
    ) -> S:
        return service_class(repo)
    return _get_service
