import { describe, expect, it } from "vitest";

import { buildAdminLocationKey, parseAdminLocationPrefill } from "./adminUrlState";

describe("adminUrlState", () => {
  it("builds users page filters into the canonical query string", () => {
    const locationKey = buildAdminLocationKey("/system/users", "users", {
      users: {
        account_id: "account-7",
        site_id: "site-3",
        lifecycle_status: "active",
        search: "alice",
        selected_user_id: "user-9",
      },
    });

    expect(locationKey).toBe(
      "/system/users?account_id=account-7&site_id=site-3&lifecycle_status=active&search=alice&selected_user_id=user-9"
    );
  });

  it("parses users page filters from the query string", () => {
    const prefill = parseAdminLocationPrefill(
      "users",
      "?account_id=account-7&site_id=site-3&lifecycle_status=active&search=alice&selected_user_id=user-9"
    );

    expect(prefill).toMatchObject({
      account_id: "account-7",
      site_id: "site-3",
      lifecycle_status: "active",
      search: "alice",
      selected_user_id: "user-9",
    });
  });
});
