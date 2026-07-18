import { useQuery } from "@tanstack/react-query";
import { getModelCapabilities, listV2Models, validateModelResolution, type ModelResolution, type V2CatalogModel } from "../../lib/api/client";

export type ReasoningLevel = "auto" | "fast" | "standard" | "deep" | "max";
export const REASONING_LEVELS: readonly ReasoningLevel[] = ["auto", "fast", "standard", "deep", "max"];
export type ModelCapability = V2CatalogModel;
export type { ModelResolution };

export function supportedReasoning(model: ModelCapability): ReasoningLevel[] {
  return model.capabilities.reasoning ? [...REASONING_LEVELS] : ["auto"];
}

export function modelKey(model: ModelCapability): string {
  return `${model.provider}/${model.model_id}`;
}

export const modelKeys = {
  catalog: (filters: { provider?: string; capability?: string } = {}) => ["v2", "models", filters] as const,
  capabilities: (provider: string, modelId: string) => ["v2", "models", provider, modelId, "capabilities"] as const,
};

export function useModelCatalog(filters: { provider?: string; capability?: string } = {}) {
  return useQuery({ queryKey: modelKeys.catalog(filters), queryFn: () => listV2Models(filters), staleTime: 300_000, retry: false });
}

export function useModelCapabilities(provider?: string, modelId?: string) {
  return useQuery({
    queryKey: modelKeys.capabilities(provider ?? "", modelId ?? ""),
    queryFn: () => getModelCapabilities(provider as string, modelId as string),
    enabled: Boolean(provider && modelId),
    staleTime: 300_000,
    retry: false,
  });
}

export function validateResolution(payload: { provider: string; model_id: string; level: ReasoningLevel }) {
  return validateModelResolution(payload);
}
