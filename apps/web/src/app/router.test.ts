import { describe, expect, it } from "vitest";
import { appPath, parseAppPath } from "./router";

describe("application routes", () => {
  it("round trips a project page through the URL", () => {
    const path = appPath({ view: "studio", projectId: "project-1" });
    expect(path).toBe("/projects/project-1/studio");
    expect(parseAppPath(path)).toEqual({ view: "studio", projectId: "project-1" });
  });

  it("keeps settings and projects addressable without a project", () => {
    expect(parseAppPath("/settings")).toEqual({ view: "settings" });
    expect(parseAppPath("/projects")).toEqual({ view: "projects" });
  });
});
