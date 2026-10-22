import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { EmailForm } from "@/components/tools/email-form";

function setup() {
  const onSubmit = vi.fn();
  const user = userEvent.setup();
  render(<EmailForm onSubmit={onSubmit} pending={false} />);
  const pickTask = (name: string) => user.click(screen.getByRole("tab", { name }));
  return { onSubmit, user, pickTask };
}

describe("EmailForm", () => {
  it("shows the tone only for Draft, Rewrite and Change tone", async () => {
    const { pickTask } = setup();
    const toneShown = () => screen.queryByRole("combobox", { name: "Tone" }) !== null;

    expect(toneShown()).toBe(true); // Draft is the default
    await pickTask("Fix grammar");
    expect(toneShown()).toBe(false);
    await pickTask("Rewrite");
    expect(toneShown()).toBe(true);
    await pickTask("Summarize thread");
    expect(toneShown()).toBe(false);
    await pickTask("Change tone");
    expect(toneShown()).toBe(true);
  });

  it("labels the text box for the chosen task", async () => {
    const { pickTask } = setup();
    expect(screen.getByLabelText("What should the email say?")).toBeInTheDocument();
    await pickTask("Summarize thread");
    expect(screen.getByLabelText("The email thread")).toBeInTheDocument();
  });

  it("sends the tone with a draft", async () => {
    const { onSubmit, user } = setup();
    await user.type(
      screen.getByLabelText("What should the email say?"),
      "Invite the team to Friday's demo",
    );
    await user.click(screen.getByRole("button", { name: "Write email" }));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit).toHaveBeenCalledWith({
      task: "draft",
      tone: "friendly",
      text: "Invite the team to Friday's demo",
    });
  });

  it("leaves the tone out where it doesn't apply", async () => {
    const { onSubmit, user, pickTask } = setup();
    await pickTask("Fix grammar");
    await user.type(screen.getByLabelText("Text to correct"), "  we is going tomorow ");
    await user.click(screen.getByRole("button", { name: "Write email" }));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit.mock.calls[0][0]).toEqual({ task: "grammar", text: "we is going tomorow" });
    expect(onSubmit.mock.calls[0][0]).not.toHaveProperty("tone");
  });

  it("requires some text", async () => {
    const { onSubmit, user } = setup();
    await user.click(screen.getByRole("button", { name: "Write email" }));
    expect(await screen.findByText("Add some text to work with")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("disables the submit while a request runs", () => {
    render(<EmailForm onSubmit={vi.fn()} pending />);
    expect(screen.getByRole("button", { name: /Writing/ })).toBeDisabled();
  });
});
