import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PRODUCT_NAME, Wordmark } from "@/components/common/wordmark";

describe("Wordmark", () => {
  it("renders the product name with a decorative coral dot", () => {
    const { container } = render(<Wordmark />);
    expect(screen.getByText(PRODUCT_NAME)).toBeInTheDocument();
    const dot = container.querySelector("[aria-hidden]");
    expect(dot).toHaveClass("bg-coral");
  });
});
