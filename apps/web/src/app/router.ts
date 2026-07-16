import { useSyncExternalStore } from "react";

export type AppView = "projects" | "studio" | "outline" | "context" | "workflow" | "settings" | "usage";
export type AppRoute = { view: AppView; projectId?: string };

const navigationEvent = "proseforge:navigate";

export function parseAppPath(pathname: string): AppRoute {
  const parts = pathname.split("/").filter(Boolean).map(value => decodeURIComponent(value));
  if (parts[0] === "projects" && !parts[1]) return { view: "projects" };
  if (parts[0] === "projects" && parts[1]) {
    const view = parts[2] as AppView | undefined;
    if (["studio", "outline", "context", "workflow"].includes(view ?? "")) return { view: view!, projectId: parts[1] };
    return { view: "studio", projectId: parts[1] };
  }
  if (parts[0] === "usage") return { view: "usage" };
  if (parts[0] === "settings") return { view: "settings" };
  return { view: "projects" };
}

export function appPath(route: AppRoute): string {
  if (route.view === "projects") return "/projects";
  if (route.view === "settings" || route.view === "usage") return `/${route.view}`;
  if (!route.projectId) return "/projects";
  return `/projects/${encodeURIComponent(route.projectId)}/${route.view}`;
}

export function navigateRoute(route: AppRoute): void {
  window.history.pushState({}, "", appPath(route));
  window.dispatchEvent(new Event(navigationEvent));
}

export function useAppRoute(): AppRoute {
  return useSyncExternalStore(
    onStoreChange => {
      window.addEventListener("popstate", onStoreChange);
      window.addEventListener(navigationEvent, onStoreChange);
      return () => {
        window.removeEventListener("popstate", onStoreChange);
        window.removeEventListener(navigationEvent, onStoreChange);
      };
    },
    () => parseAppPath(window.location.pathname),
    () => ({ view: "projects" }),
  );
}
