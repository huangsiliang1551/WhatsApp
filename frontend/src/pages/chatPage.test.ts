import { describe, expect, it } from "vitest";

import { getConversationTabLabel } from "./ChatPage";

describe("getConversationTabLabel", () => {
  it("prefers public user id when present", () => {
    expect(
      getConversationTabLabel({
        customer_id: "user-1",
        customer_public_user_id: "pub-u1",
      } as never),
    ).toBe("pub-u1");
  });

  it("falls back to customer id when public user id is missing", () => {
    expect(
      getConversationTabLabel({
        customer_id: "user-1",
      } as never),
    ).toBe("user-1");
  });
});
