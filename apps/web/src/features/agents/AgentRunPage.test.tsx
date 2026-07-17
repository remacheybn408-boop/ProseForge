import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AgentRunPage } from "./AgentRunPage";
describe("AgentRunPage", () => { it("shows role/status stamps and controls do not write chapters", () => { const onAction = vi.fn(); render(<AgentRunPage status="PAUSED" onAction={onAction} tasks={[{ id: "t1", role: "Scene Writer", status: "done", attempts: 1 }]} />); expect(screen.getByText("PAUSED")).toBeTruthy(); expect(screen.getAllByText("Scene Writer")).toHaveLength(2); fireEvent.click(screen.getByRole("button", { name: "resume" })); expect(onAction).toHaveBeenCalledWith("resume"); }); });
