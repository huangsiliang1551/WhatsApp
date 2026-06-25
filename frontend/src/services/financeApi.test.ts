import { beforeEach, describe, expect, it, vi } from "vitest";

const hoisted = vi.hoisted(() => ({
  getMock: vi.fn(),
  postMock: vi.fn(),
}));

vi.mock("./api", () => ({
  api: {
    get: hoisted.getMock,
    post: hoisted.postMock,
  },
}));

import {
  getFinanceSummary,
  listRechargeRecords,
  listWithdrawalRecords,
} from "./financeApi";

describe("financeApi", () => {
  beforeEach(() => {
    hoisted.getMock.mockReset();
    hoisted.postMock.mockReset();
  });

  it("passes site and bonus filters to recharge records endpoint", async () => {
    hoisted.getMock.mockResolvedValue({ data: [] });

    await listRechargeRecords({
      agencyId: "acct-1",
      siteId: "site-1",
      status: "paid",
      sourceType: "manual_real_recharge",
      fundScope: "cash",
      includeBonus: false,
      sortField: "created_at",
      sortOrder: "desc",
    });

    expect(hoisted.getMock).toHaveBeenCalledWith("/api/finance/recharge-records", {
      params: {
        agency_id: "acct-1",
        site_id: "site-1",
        status: "paid",
        source_type: "manual_real_recharge",
        fund_scope: "cash",
        include_bonus: false,
        sort_field: "created_at",
        sort_order: "desc",
      },
    });
  });

  it("passes site and bonus filters to withdrawal records endpoint", async () => {
    hoisted.getMock.mockResolvedValue({ data: [] });

    await listWithdrawalRecords({
      agencyId: "acct-2",
      siteId: "site-2",
      status: "paid",
      fundScope: "bonus",
      includeBonus: true,
      sortField: "amount",
      sortOrder: "asc",
    });

    expect(hoisted.getMock).toHaveBeenCalledWith("/api/finance/withdrawal-records", {
      params: {
        agency_id: "acct-2",
        site_id: "site-2",
        status: "paid",
        fund_scope: "bonus",
        include_bonus: true,
        sort_field: "amount",
        sort_order: "asc",
      },
    });
  });

  it("keeps finance summary query mapped to backend params", async () => {
    hoisted.getMock.mockResolvedValue({ data: { recharge_amount: 0 } });

    await getFinanceSummary({
      agencyId: "acct-3",
      includeBonus: false,
    });

    expect(hoisted.getMock).toHaveBeenCalledWith("/api/finance/report/summary", {
      params: {
        agency_id: "acct-3",
        include_bonus: false,
      },
    });
  });
});
