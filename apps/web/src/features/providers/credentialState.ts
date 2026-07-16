import type { Credential } from "../../lib/api/client";

export function upsertCredential(credentials: Credential[], next: Credential): Credential[] {
  const index = credentials.findIndex(item => item.id === next.id || item.provider === next.provider);
  if (index < 0) return [...credentials, next];
  return credentials.map((item, currentIndex) => currentIndex === index ? next : item);
}

export function removeCredential(credentials: Credential[], credentialId: string): Credential[] {
  return credentials.filter(item => item.id !== credentialId);
}
