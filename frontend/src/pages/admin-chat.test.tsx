import { describe, expect, it } from "vitest";

import { ConversationList, MessagePanel, QuickToolbar } from "./admin-chat";

describe("admin-chat exports", () => {
  it("exposes conversation list", () => {
    expect(ConversationList).toBeTruthy();
  });

  it("exposes message panel", () => {
    expect(MessagePanel).toBeTruthy();
  });

  it("exposes quick toolbar", () => {
    expect(QuickToolbar).toBeTruthy();
  });
});
