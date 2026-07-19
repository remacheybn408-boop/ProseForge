import { fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import type { ReactElement } from "react";
import { describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../../lib/i18n";
import { ExportDialog } from "./ExportDialog";

function renderDialog(dialog: ReactElement) {
  return render(<I18nProvider locale="en">{dialog}</I18nProvider>);
}

describe("ExportDialog", () => {
  it("submits format, range, immutable version and preset", () => {
    const onExport = vi.fn();
    renderDialog(<ExportDialog projectId="p1" versionIds={["v1", "v2"]} onExport={onExport} />);
    fireEvent.change(screen.getByLabelText("Export format"), { target: { value: "epub" } });
    fireEvent.click(screen.getByLabelText("Submission"));
    fireEvent.change(screen.getByLabelText("Chapter range start"), { target: { value: "2" } });
    fireEvent.change(screen.getByLabelText("Chapter range end"), { target: { value: "4" } });
    fireEvent.submit(screen.getByRole("form"));
    expect(onExport.mock.calls[0][0]).toMatchObject({ project_id: "p1", format: "epub", template: "submission", chapter_range: [2, 4], version_ids: ["v1"] });
  });
  it("shows the server-computed file hash", () => {
    renderDialog(<ExportDialog projectId="p1" versionIds={["v1"]} onExport={vi.fn()} manifest={{ id: "m1", project_id: "p1", format: "md", template: "archive", locale: "zh-CN", version_ids: ["v1"], content_hashes: { v1: "source" }, file_sha256: "abc123", byte_size: 42, download_url: "/download" }} />);
    expect(screen.getByText("abc123")).not.toBeNull();
    expect(screen.getByText(/42 bytes/)).not.toBeNull();
  });
  it("closes with Escape", () => {
    const onClose = vi.fn();
    renderDialog(<ExportDialog projectId="p1" versionIds={[]} onExport={vi.fn()} onClose={onClose} />);
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
  });
});
