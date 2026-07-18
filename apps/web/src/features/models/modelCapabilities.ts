export type ReasoningLevel = "auto" | "fast" | "standard" | "deep" | "max";
export type ModelCapability = { provider: string; model_id: string; context_window?: number | null; max_output_tokens?: number | null; capabilities: Record<string, unknown> };

export function supportedReasoning(model: ModelCapability): ReasoningLevel[] {
  return model.capabilities.reasoning ? ["auto", "fast", "standard", "deep", "max"] : ["auto"];
}
