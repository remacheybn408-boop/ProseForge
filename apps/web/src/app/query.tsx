import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { getHealth, getUsageSummary, listModels, listProjects, listProviders, type Project } from "../lib/api/client";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

export function AppQueryProvider({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

export function useProjectsQuery() {
  return useQuery<Project[]>({ queryKey: ["projects"], queryFn: listProjects, retry: false });
}

export function useHealthQuery() {
  return useQuery({ queryKey: ["health"], queryFn: getHealth, retry: 1, refetchInterval: 30_000 });
}

export function useUsageSummaryQuery(projectId?: string) {
  return useQuery({ queryKey: ["usage", "summary", projectId ?? "user"], queryFn: () => getUsageSummary(projectId ? { project_id: projectId } : {}), enabled: Boolean(projectId) });
}

export function useProvidersQuery() {
  return useQuery({ queryKey: ["providers"], queryFn: listProviders, staleTime: 300_000 });
}

export function useModelsQuery(provider?: string) {
  return useQuery({ queryKey: ["models", provider ?? "all"], queryFn: () => listModels(provider ? { provider } : {}), enabled: Boolean(provider), staleTime: 300_000 });
}
