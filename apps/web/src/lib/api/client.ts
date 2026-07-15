export type Project = { id: string; slug: string; title: string; genre: string; style: string; language: string; status: string };
export type Credential = { id: string; provider: string; masked_key: string };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, { ...init, credentials: "include", headers: { "content-type": "application/json", ...(init?.headers ?? {}) } });
  if (!response.ok) throw new Error(`API ${response.status}`);
  return response.json() as Promise<T>;
}

export function getHealth() { return request<{ status: string }>("/api/v1/health/live"); }
export function listProjects() { return request<Project[]>("/api/v1/projects"); }
export function listCredentials() { return request<Credential[]>("/api/v1/credentials"); }
export function saveCredential(payload: { provider: string; api_key: string; base_url?: string }) { return request<Credential>("/api/v1/credentials", { method: "POST", body: JSON.stringify(payload) }); }
