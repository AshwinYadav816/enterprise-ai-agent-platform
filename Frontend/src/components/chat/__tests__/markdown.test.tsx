import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Markdown } from "@/components/chat/markdown";
import { cleanSnippet, linkCitations } from "@/lib/chat/citations";
import type { Source } from "@/lib/chat/types";

const SOURCES: Source[] = [
  { n: 1, doc_id: "d1", filename: "leave-policy.pdf", page: 1, snippet: "24 days of paid leave" },
  { n: 2, doc_id: "d2", filename: "handbook.pdf", page: null, snippet: "Remote work" },
];

describe("Markdown citations", () => {
  it("turns [1] into a citation chip only when source 1 exists", () => {
    render(
      <Markdown sources={SOURCES}>
        {"You get 24 days [1]. Remote is fine [2]. See also [3]."}
      </Markdown>,
    );
    expect(
      screen.getByRole("button", { name: "Source 1: leave-policy.pdf, page 1" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Source 2: handbook.pdf" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Source 3/ })).not.toBeInTheDocument();
    expect(screen.getByText(/See also \[3\]\./)).toBeInTheDocument();
  });

  it("renders no chips without sources", () => {
    render(<Markdown>{"A fake answer [1]."}</Markdown>);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.getByText("A fake answer [1].")).toBeInTheDocument();
  });

  it("leaves [n] inside code alone", () => {
    expect(linkCitations("use `arr[1]` here [1]\n```\nx = a[2]\n```", SOURCES)).toBe(
      "use `arr[1]` here [1](#cite-1)\n```\nx = a[2]\n```",
    );
  });

  it("never renders raw HTML", () => {
    const { container } = render(
      <Markdown sources={SOURCES}>
        {'Hi <b>bold</b> <img src=x onerror="alert(1)"> <script>alert(1)</script> [1]'}
      </Markdown>,
    );
    expect(container.querySelector("b, img, script")).toBeNull();
    expect(container.textContent).toContain("<b>bold</b>");
  });

  it("only allows safe link targets", () => {
    const { container } = render(
      <Markdown>{"[click](javascript:alert(1)) [ok](https://example.org)"}</Markdown>,
    );
    const hrefs = [...container.querySelectorAll("a")].map((a) => a.getAttribute("href"));
    expect(hrefs).not.toContain("javascript:alert(1)");
    expect(hrefs).toContain("https://example.org");
  });

  it("renders GFM tables", () => {
    render(<Markdown>{"| Task | Owner |\n|---|---|\n| Notes | Rohit |"}</Markdown>);
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "Rohit" })).toBeInTheDocument();
  });

  it("drops the passage marker from snippets", () => {
    expect(cleanSnippet("[leave-policy.pdf — p.1] Acme Leave Policy 2026")).toBe(
      "Acme Leave Policy 2026",
    );
    expect(cleanSnippet("No marker [1] here")).toBe("No marker [1] here");
  });
});
