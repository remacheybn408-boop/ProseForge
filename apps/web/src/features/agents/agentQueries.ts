export type AgentRun = { id: string; status: string; checkpoint_id?: string; budget_used?: number; budget_limit?: number };
export type AgentTask = { id: string; role: string; status: string; attempts: number };
