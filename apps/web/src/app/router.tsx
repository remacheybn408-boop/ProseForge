import { createRouter, Navigate } from "@tanstack/react-router";
import { routeTree } from "./routes";

export const router = createRouter({
  routeTree,
  defaultNotFoundComponent: () => <Navigate to="/projects" />,
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
