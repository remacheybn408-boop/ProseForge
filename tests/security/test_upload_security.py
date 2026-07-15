import pytest

from proseforge.application.files.upload_service import validate_upload


def test_upload_rejects_traversal():
    with pytest.raises(ValueError):
        validate_upload("../secret.txt", b"x", "text/plain")
