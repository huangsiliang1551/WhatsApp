import { describe, expect, it } from "vitest";

import { getForwardConversationOptionLabel } from "./MessagePanel";

describe("getForwardConversationOptionLabel", () => {
  it("prefers public user id when present", () => {
    expect(
      getForwardConversationOptionLabel({
        customer_id: "user-1",
        customer_public_user_id: "pub-u1",
        last_message_preview: "hello world",
      } as never),
    ).toContain("pub-u1");
  });

  it("falls back to customer id when public user id is missing", () => {
    expect(
      getForwardConversationOptionLabel({
        customer_id: "user-1",
        last_message_preview: "hello world",
      } as never),
    ).toContain("user-1");
  });
});
