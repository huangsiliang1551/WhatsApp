import { describe, expect, it } from "vitest";

import sitesPageSource from "./SitesPage.tsx?raw";
import {
  FIXED_DEFAULT_H5_TEMPLATE_MESSAGE,
  buildFixedH5SiteCreatePayload,
} from "./SitesPage";

describe("SitesPage fixed H5 flow", () => {
  it("injects the fixed default template id into the create payload", () => {
    expect(
      buildFixedH5SiteCreatePayload(
        {
          site_key: "site-a",
          domain: "example.com",
          brand_name: "Example",
          default_language: "zh-CN",
          status: "active",
        },
        "tpl-default"
      )
    ).toEqual({
      site_key: "site-a",
      domain: "example.com",
      brand_name: "Example",
      default_language: "zh-CN",
      status: "active",
      template_id: "tpl-default",
    });
  });

  it("keeps a user-facing message explaining the fixed default H5 template", () => {
    expect(FIXED_DEFAULT_H5_TEMPLATE_MESSAGE).toContain("固定默认 H5");
  });

  it("does not keep template selection or template switching source hooks in SitesPage", () => {
    expect(sitesPageSource).not.toContain('key: "change-template"');
    expect(sitesPageSource).not.toContain('name="template_id"');
    expect(sitesPageSource).not.toContain("handleConfirmChangeTemplate");
  });
});
