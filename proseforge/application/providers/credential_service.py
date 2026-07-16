from __future__ import annotations

import json
from dataclasses import dataclass

from proseforge.infrastructure.security.credential_cipher import CredentialCipher


@dataclass(frozen=True)
class CredentialView:
    credential_id: str
    provider: str
    masked_key: str


class CredentialService:
    def __init__(self, cipher: CredentialCipher):
        self.cipher = cipher
        self._records: dict[str, tuple[str, bytes, str]] = {}

    def save(self, credential_id: str, user_id: str, provider: str, api_key: str) -> CredentialView:
        associated_data = f"{user_id}:{provider}:{credential_id}".encode()
        encrypted = self.cipher.encrypt(json.dumps({"api_key": api_key}).encode(), associated_data=associated_data)
        self._records[credential_id] = (provider, encrypted, user_id)
        return CredentialView(credential_id, provider, self._mask(api_key))

    def view(self, credential_id: str, user_id: str) -> CredentialView:
        provider, encrypted, owner = self._records[credential_id]
        if owner != user_id:
            raise PermissionError("credential belongs to another user")
        associated_data = f"{user_id}:{provider}:{credential_id}".encode()
        payload = json.loads(self.cipher.decrypt(encrypted, associated_data=associated_data))
        return CredentialView(credential_id, provider, self._mask(str(payload["api_key"])))

    @staticmethod
    def _mask(value: str) -> str:
        return f"{value[:3]}****{value[-4:]}" if len(value) > 7 else "****"
