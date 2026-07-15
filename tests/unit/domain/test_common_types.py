from datetime import UTC

from proseforge.domain.common.ids import new_id
from proseforge.domain.common.result import OperationResult


def test_new_id_is_lexically_sortable_string() -> None:
    first = new_id()
    second = new_id()
    assert isinstance(first, str)
    assert len(first) >= 20
    assert first < second


def test_operation_result_success() -> None:
    result = OperationResult.ok({"value": 1})
    assert result.success is True
    assert result.data == {"value": 1}
    assert result.errors == ()
