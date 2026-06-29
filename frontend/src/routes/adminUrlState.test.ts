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

  it("builds and parses customers detail tab prefill", () => {
    const locationKey = buildAdminLocationKey("/system/customers", "customers", {
      customers: {
        account_id: "account-3",
        query: "pub-u3",
        selected_profile_id: "user-3",
        detail_tab: "finance",
      },
    });

    expect(locationKey).toBe(
      "/system/customers?account_id=account-3&query=pub-u3&selected_profile_id=user-3&detail_tab=finance"
    );

    const prefill = parseAdminLocationPrefill(
      "customers",
      "?account_id=account-3&query=pub-u3&selected_profile_id=user-3&detail_tab=finance"
    );

    expect(prefill).toMatchObject({
      account_id: "account-3",
      query: "pub-u3",
      selected_profile_id: "user-3",
      detail_tab: "finance",
    });
  });
});
