import os

import pytest

from proseforge.application.providers.credential_service import CredentialService
from proseforge.infrastructure.security.credential_cipher import CredentialCipher


def test_credential_service_never_returns_plaintext():
    service = CredentialService(CredentialCipher(os.urandom(32)))
    view = service.save("c1", "u1", "openai", "sk-super-secret-key")
    assert view.masked_key == "sk-****-key"
    assert "secret" not in view.masked_key
    assert service.view("c1", "u1").masked_key == view.masked_key
    with pytest.raises(PermissionError):
        service.view("c1", "u2")
