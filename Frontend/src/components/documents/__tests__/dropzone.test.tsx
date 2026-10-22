import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Dropzone, splitFiles } from "@/components/documents/dropzone";
import { MAX_UPLOAD_BYTES } from "@/lib/documents";

/** A File whose reported size we control without allocating megabytes. */
function fakeFile(name: string, size: number, type = "application/octet-stream"): File {
  const file = new File(["x"], name, { type });
  Object.defineProperty(file, "size", { value: size });
  return file;
}

describe("Dropzone", () => {
  it("accepts pdf, docx, pptx and xlsx (any case) within the size limit", () => {
    const files = ["a.pdf", "b.docx", "c.PPTX", "d.xlsx"].map((n) => fakeFile(n, 2048));
    const { accepted, rejected } = splitFiles(files);
    expect(accepted.map((f) => f.name)).toEqual(["a.pdf", "b.docx", "c.PPTX", "d.xlsx"]);
    expect(rejected).toEqual([]);
  });

  it("rejects wrong extensions, oversize and empty files with a reason", () => {
    const { accepted, rejected } = splitFiles([
      fakeFile("notes.txt", 100),
      fakeFile("archive", 100),
      fakeFile("big.pdf", MAX_UPLOAD_BYTES + 1),
      fakeFile("empty.pdf", 0),
      fakeFile("limit.pdf", MAX_UPLOAD_BYTES),
    ]);
    expect(accepted.map((f) => f.name)).toEqual(["limit.pdf"]);
    expect(rejected.map((r) => [r.file.name, r.reason])).toEqual([
      ["notes.txt", ".txt files aren't supported. Use PDF, Word, PowerPoint or Excel."],
      ["archive", "This file has no extension. Use PDF, Word, PowerPoint or Excel."],
      ["big.pdf", "This file is larger than 25 MB."],
      ["empty.pdf", "This file is empty."],
    ]);
  });

  it("reports picked files through onFiles (browse)", async () => {
    const onFiles = vi.fn();
    render(<Dropzone onFiles={onFiles} />);
    const input = screen.getByTestId("file-input");
    await userEvent.upload(input, [fakeFile("policy.pdf", 1000), fakeFile("photo.png", 1000)], {
      applyAccept: false,
    });
    expect(onFiles).toHaveBeenCalledTimes(1);
    const [accepted, rejected] = onFiles.mock.calls[0];
    expect(accepted.map((f: File) => f.name)).toEqual(["policy.pdf"]);
    expect(rejected.map((r: { file: File }) => r.file.name)).toEqual(["photo.png"]);
  });

  it("reports dropped files, and ignores drops while disabled", () => {
    const onFiles = vi.fn();
    const { rerender } = render(<Dropzone onFiles={onFiles} />);
    const zone = screen.getByTestId("dropzone");
    const drop = (files: File[]) => fireEvent.drop(zone, { dataTransfer: { files } });

    drop([fakeFile("q3.xlsx", 5000)]);
    expect(onFiles).toHaveBeenCalledWith([expect.objectContaining({ name: "q3.xlsx" })], []);

    rerender(<Dropzone onFiles={onFiles} disabled />);
    drop([fakeFile("q4.xlsx", 5000)]);
    expect(onFiles).toHaveBeenCalledTimes(1);
  });
});
