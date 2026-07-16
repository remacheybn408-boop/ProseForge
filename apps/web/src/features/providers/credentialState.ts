import type { Credential } from "../../lib/api/client";

export function upsertCredential(credentials: Credential[], next: Credential): Credential[] {
  return [...credentials.filter(item => item.id !== next.id && item.provider !== next.provider), next];
}

export function removeCredential(credentials: Credential[], credentialId: string): Credential[] {
  return credentials.filter(item => item.id !== credentialId);
}
