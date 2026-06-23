import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  createRechargeOrder,
  createWithdrawRequest,
  getMessagesApi,
  listMemberMessages,
  listTaskPackages,
  registerMember,
} from "./h5Member";

const MEMBER_SESSION_KEY = "frontend.h5.member-session.v1";

const SESSION = {
  accountId: "38271456",
  phone: "13800000000",
  publicUserId: "h5-38271456",
  displayName: "Demo Member",
  inviteCode: "INV-ABCD1234",
};

function installLocalStorageMock(): void {
  const storage = new Map<string, string>();
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    value: {
      getItem(key: string): string | null {
        return storage.get(key) ?? null;
      },
      setItem(key: string, value: string): void {
        storage.set(key, value);
      },
      removeItem(key: string): void {
        storage.delete(key);
      },
      clear(): void {
        storage.clear();
      },
    },
  });
}

function seedSession(): void {
  window.localStorage.setItem(MEMBER_SESSION_KEY, JSON.stringify(SESSION));
}

describe("h5Member i18n service errors", () => {
  beforeEach(() => {
    installLocalStorageMock();
    window.localStorage.clear();
    window.localStorage.setItem("h5-lang", "en");
    vi.unstubAllEnvs();
  });

  it("localizes auth-required errors using the active language at call time", async () => {
    await expect(createRechargeOrder(10)).rejects.toThrow("Please log in to your member account first.");
  });

  it("localizes recharge validation errors in English", async () => {
    seedSession();

    await expect(createRechargeOrder(0)).rejects.toThrow("Recharge amount must be greater than 0.");
  });

  it("localizes withdraw validation errors in English", async () => {
    seedSession();

    await expect(createWithdrawRequest(0)).rejects.toThrow("Withdrawal amount must be greater than 0.");
  });

  it("writes localized english notification messages for successful recharge and withdrawal flows", async () => {
    seedSession();

    await createRechargeOrder(25);
    await createWithdrawRequest(20);
    const messages = await listMemberMessages();

    expect(messages[0]?.title).toBe("Withdrawal request submitted");
    expect(messages[0]?.body).toBe("Funds are under review. Check this page and your balance records for status updates.");
    expect(messages[1]?.title).toBe("Recharge successful");
    expect(messages[1]?.body).toBe("System balance increased by 25.00.");
  });

  it("returns localized english seed task packages and message center content", async () => {
    seedSession();

    const taskPackages = await listTaskPackages();
    const messages = await listMemberMessages();

    expect(taskPackages[0]?.title).toBe("Rookie Task Package");
    expect(taskPackages[0]?.description).toBe(
      "Complete your first batch of order tasks to unlock task balance and fragment rewards.",
    );
    expect(messages[0]?.title).toBe("Fragments available from check-in");
    expect(messages[0]?.body).toBe(
      "Today’s check-in can grant 1 random fragment. Collect the full set to request a shipping reward.",
    );
  });
  it("localizes english defaults for legacy registration and mock chat seed messages", async () => {
    const profile = await registerMember({
      siteKey: "demo",
      phone: "15500001234",
      password: "demo123456",
    });
    const chat = await getMessagesApi({});

    expect(profile.displayName).toBe(`Member ${profile.accountId.slice(-4)}`);
    expect(chat.items[0]?.content).toBe("Hello, welcome to customer support.");
    expect(chat.items[1]?.content).toBe("Hi, I need help with an issue.");
    expect(chat.items[2]?.content).toBe("Please describe the issue and I will assist you.");
  });
});
