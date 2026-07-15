from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class OperationResult(Generic[T]):
    success: bool
    data: T | None
    warnings: tuple[dict[str, object], ...]
    errors: tuple[dict[str, object], ...]

    @classmethod
    def ok(cls, data: T) -> "OperationResult[T]":
        return cls(True, data, (), ())

    @classmethod
    def fail(
        cls,
        *,
        code: str,
        message: str,
        retryable: bool = False,
    ) -> "OperationResult[T]":
        return cls(
            False,
            None,
            (),
            ({"code": code, "message": message, "retryable": retryable},),
        )
