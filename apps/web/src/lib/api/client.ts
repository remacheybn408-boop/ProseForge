export type Project = { id: string; slug: string; title: string; genre: string; style: string; language: string; status: string };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, { ...init, credentials: "include", headers: { "content-type": "application/json", ...(init?.headers ?? {}) } });
  if (!response.ok) throw new Error(`API ${response.status}`);
  return response.json() as Promise<T>;
}

export function getHealth() { return request<{ status: string }>("/api/v1/health/live"); }
export function listProjects() { return request<Project[]>("/api/v1/projects"); }
