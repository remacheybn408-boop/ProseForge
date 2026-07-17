import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ExportDialog } from "./ExportDialog";
describe("ExportDialog", () => { it("exports selected immutable versions", () => { const onExport = vi.fn(); render(<ExportDialog projectId="p1" versionIds={["v1"]} onExport={onExport} />); fireEvent.change(screen.getByLabelText("Export format"), { target: { value: "epub" } }); fireEvent.submit(screen.getByRole("form")); expect(onExport.mock.calls[0][0]).toMatchObject({ project_id: "p1", format: "epub", version_ids: ["v1"] }); }); });
