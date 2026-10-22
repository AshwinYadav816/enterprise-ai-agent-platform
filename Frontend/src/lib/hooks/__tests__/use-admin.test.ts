import { describe, expect, it } from "vitest";

import { actionLabel, activityTarget, type AuditEntry } from "@/lib/hooks/use-admin";

function entry(
  action: string,
  meta: Record<string, unknown> | null,
  target_id: string | null = null,
): AuditEntry {
  return {
    id: "a1",
    action,
    user_id: "u1",
    user_email: "admin@acme-demo.com",
    target_type: null,
    target_id,
    meta,
    ip: "127.0.0.1",
    created_at: "2026-10-22T12:00:00Z",
  };
}

const names = new Map([["u2", "Mina Manager"]]);

describe("activity display", () => {
  it("labels known actions and falls back to the raw string", () => {
    expect(actionLabel("auth.login")).toBe("Signed in");
    expect(actionLabel("user.role_changed")).toBe("Changed a role");
    expect(actionLabel("something.new")).toBe("something.new");
  });

  it("describes what each action was about", () => {
    expect(
      activityTarget(entry("document.uploaded", { filename: "plan.pdf", size_bytes: 9 }), names),
    ).toBe("plan.pdf");
    expect(
      activityTarget(entry("user.created", { email: "eli@acme.com", role: "employee" }), names),
    ).toBe("eli@acme.com as employee");
    expect(
      activityTarget(entry("user.role_changed", { from: "employee", to: "manager" }, "u2"), names),
    ).toBe("Mina Manager: employee → manager");
    expect(activityTarget(entry("user.deactivated", null, "u9"), names)).toBe("a user");
    expect(activityTarget(entry("generation.created", { kind: "document_insights" }), names)).toBe(
      "document insights",
    );
    expect(activityTarget(entry("auth.login", null), names)).toBe("");
  });
});
