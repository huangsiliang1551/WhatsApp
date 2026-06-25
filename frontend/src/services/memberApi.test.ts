import { beforeEach, describe, expect, it, vi } from "vitest";

const hoisted = vi.hoisted(() => ({
  getCustomerSummaryMock: vi.fn(),
}));

vi.mock("./api", () => ({
  getCustomerSummary: hoisted.getCustomerSummaryMock,
}));

import { getMemberSummary } from "./memberApi";

describe("memberApi", () => {
  beforeEach(() => {
    hoisted.getCustomerSummaryMock.mockReset();
  });

  it("delegates member summary lookup to customer summary api", async () => {
    hoisted.getCustomerSummaryMock.mockResolvedValue({ customer: { id: "user-1" } });

    const result = await getMemberSummary("user-1", "acct-1");

    expect(hoisted.getCustomerSummaryMock).toHaveBeenCalledWith("user-1", "acct-1");
    expect(result).toEqual({ customer: { id: "user-1" } });
  });
});
