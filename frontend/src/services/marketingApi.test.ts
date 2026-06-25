import { beforeEach, describe, expect, it, vi } from "vitest";

const hoisted = vi.hoisted(() => ({
  getMock: vi.fn(),
  putMock: vi.fn(),
}));

vi.mock("./api", () => ({
  api: {
    get: hoisted.getMock,
    put: hoisted.putMock,
  },
}));

describe("marketingApi invite config mapping", () => {
  beforeEach(() => {
    hoisted.getMock.mockReset();
    hoisted.putMock.mockReset();
  });

  it("normalizes backend invite config fields into the frontend shape", async () => {
    hoisted.getMock.mockResolvedValueOnce({
      data: {
        register_reward: 2,
        recharge_threshold: 30,
        recharge_reward: 3,
        max_count: 20,
        anti_fraud_same_ip_limit: 3,
        anti_fraud_same_device_limit: 2,
      },
    });

    const { getInviteConfig } = await import("./marketingApi");
    const config = await getInviteConfig();

    expect(config).toEqual({
      register_reward: 2,
      recharge_trigger_amount: 30,
      recharge_reward: 3,
      max_invitees: 20,
      same_ip_limit: 3,
      same_device_limit: 2,
    });
  });

  it("serializes the frontend invite config shape back to the backend payload", async () => {
    hoisted.putMock.mockResolvedValueOnce({ data: {} });

    const { updateInviteConfig } = await import("./marketingApi");
    await updateInviteConfig({
      register_reward: 2,
      recharge_trigger_amount: 30,
      recharge_reward: 3,
      max_invitees: 20,
      same_ip_limit: 3,
      same_device_limit: 2,
    });

    expect(hoisted.putMock).toHaveBeenCalledWith("/api/invites/config", {
      register_reward: 2,
      recharge_threshold: 30,
      recharge_reward: 3,
      max_count: 20,
      anti_fraud_same_ip_limit: 3,
      anti_fraud_same_device_limit: 2,
    });
  });

  it("loads invite relations from the dedicated backend endpoint", async () => {
    hoisted.getMock.mockResolvedValueOnce({
      data: {
        items: [{ id: "invite-1" }],
        total: 1,
        page: 1,
        size: 20,
      },
    });

    const { listInviteRelations } = await import("./marketingApi");
    const result = await listInviteRelations({ account_id: "acct-1", page: 1, size: 20 });

    expect(hoisted.getMock).toHaveBeenCalledWith("/api/invites/relations", {
      params: { account_id: "acct-1", page: 1, size: 20 },
    });
    expect(result.total).toBe(1);
  });

  it("loads invite rewards from the dedicated backend endpoint", async () => {
    hoisted.getMock.mockResolvedValueOnce({
      data: {
        items: [{ id: "reward-1" }],
        total: 1,
        page: 1,
        size: 20,
      },
    });

    const { listInviteRewards } = await import("./marketingApi");
    const result = await listInviteRewards({ account_id: "acct-1", is_rewarded: true });

    expect(hoisted.getMock).toHaveBeenCalledWith("/api/invites/rewards", {
      params: { account_id: "acct-1", is_rewarded: true },
    });
    expect(result.total).toBe(1);
  });
});
