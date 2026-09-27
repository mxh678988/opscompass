"""通用响应结构。"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一响应体。"""

    code: int = 0
    message: str = "ok"
    data: T | None = None


class PageResult(BaseModel, Generic[T]):
    """分页结果。"""

    total: int = 0
    page: int = 1
    page_size: int = 20
    items: list[T] = []
