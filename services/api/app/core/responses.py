from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


def ok(data: Any = None, message: str = "OK") -> dict[str, Any]:
    body: dict[str, Any] = {"success": True, "message": message}
    if data is not None:
        body["data"] = data
    return body


def ok_paginated(
    data: list[Any],
    *,
    page: int,
    per_page: int,
    total: int,
    message: str = "OK",
) -> dict[str, Any]:
    return {
        "success": True,
        "message": message,
        "data": data,
        "meta": {"page": page, "per_page": per_page, "total": total},
    }


def err(message: str, errors: Any | None = None, code: str = "error") -> dict[str, Any]:
    body: dict[str, Any] = {"success": False, "message": message, "code": code}
    if errors is not None:
        body["errors"] = errors
    return body


def dump_model(m: BaseModel | None) -> Any:
    if m is None:
        return None
    return m.model_dump(mode="json")


def dump_models(models: list[BaseModel]) -> list[Any]:
    return [m.model_dump(mode="json") for m in models]
