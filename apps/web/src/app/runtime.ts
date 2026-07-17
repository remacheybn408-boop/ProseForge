export type RuntimeProfile = "native" | "server" | "test";

export type RuntimeConfig = {
  api_base_url: string;
  profile: RuntimeProfile;
};

type RuntimeFetcher = (
  input: RequestInfo | URL,
  init?: RequestInit,
) => Promise<Response>;

export async function loadRuntimeConfig(
  fetcher: RuntimeFetcher = fetch,
): Promise<RuntimeConfig> {
  const response = await fetcher("/runtime-config.json", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Unable to load runtime configuration (${response.status})`);
  }
  const value = await response.json() as Partial<RuntimeConfig>;
  if (
    typeof value.api_base_url !== "string" ||
    !value.api_base_url.startsWith("/") ||
    !["native", "server", "test"].includes(value.profile ?? "")
  ) {
    throw new Error("Invalid runtime configuration");
  }
  return value as RuntimeConfig;
}
