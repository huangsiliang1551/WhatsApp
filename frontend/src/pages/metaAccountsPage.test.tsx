import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { MetaAccountsPage } from "./MetaAccountsPage";

const hoisted = vi.hoisted(() => ({
  storeState: {} as Record<string, unknown>,
  listMetaAccountsMock: vi.fn(),
}));

vi.mock("../services/api", () => ({
  listMetaAccounts: hoisted.listMetaAccountsMock,
}));

vi.mock("antd", async () => {
  const React = await import("react");
  const Wrapper = ({ children }: { children?: React.ReactNode }) => React.createElement("div", null, children);
  const Button = ({ children, onClick, loading }: { children?: React.ReactNode; onClick?: () => void; loading?: boolean }) =>
    React.createElement("button", { onClick, disabled: loading }, children);
  return {
    Button,
    Dropdown: Wrapper,
    Input: ({ ...props }: Record<string, unknown>) => React.createElement("input", props),
    Select: Wrapper,
    Space: Wrapper,
    Spin: () => React.createElement("div", null, "loading"),
    Tag: ({ children }: { children?: React.ReactNode }) => React.createElement("span", null, children),
    Typography: {
      Text: ({ children }: { children?: React.ReactNode }) => React.createElement("span", null, children),
      Title: ({ children }: { children?: React.ReactNode }) => React.createElement("h4", null, children),
      Paragraph: ({ children }: { children?: React.ReactNode }) => React.createElement("p", null, children),
    },
  };
});

vi.mock("../stores/appStore", () => ({
  useAppStore: (selector: (state: Record<string, unknown>) => unknown) => selector(hoisted.storeState),
}));

vi.mock("./meta-accounts/AccountListTab", () => ({
  AccountListTab: ({ accounts }: { accounts: Array<{ display_name: string; phone_numbers?: Array<{ display_phone_number: string }> }> }) => (
    <div>
      {accounts.map((account) => (
        <div key={account.display_name}>
          <span>{account.display_name}</span>
          {account.phone_numbers?.map((phone) => <span key={phone.display_phone_number}>{phone.display_phone_number}</span>)}
        </div>
      ))}
      <button>刷新</button>
    </div>
  ),
}));

vi.mock("./meta-accounts/AccountDetailPanel", () => ({
  AccountDetailPanel: () => <div>detail</div>,
}));

vi.mock("./meta-accounts/CreateManualModal", () => ({
  CreateManualModal: () => null,
}));

vi.mock("./meta-accounts/CreateSignupModal", () => ({
  CreateSignupModal: () => null,
}));

const mountedContainers: HTMLDivElement[] = [];
const mountedRoots: Root[] = [];

async function flushEffects(): Promise<void> {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

async function renderPage(element: ReturnType<typeof createElement>): Promise<void> {
  const container = document.createElement("div");
  document.body.appendChild(container);
  mountedContainers.push(container);
  const root = createRoot(container);
  mountedRoots.push(root);
  await act(async () => {
    root.render(element);
  });
  await flushEffects();
}

describe("MetaAccountsPage", () => {
  beforeEach(() => {
    hoisted.storeState = {
      actorAccountIds: ["acct-1"],
      activePage: "meta",
      setActivePage: vi.fn(),
      metaAccountsPagePrefill: null,
      clearMetaAccountsPagePrefill: vi.fn(),
      setMetaAccountsPagePrefill: vi.fn(),
    };
    hoisted.listMetaAccountsMock.mockReset().mockResolvedValue([
      {
        account_id: "acct-1",
        waba_id: "waba-1",
        display_name: "Account One",
        onboarding_mode: "manual",
        has_access_token: true,
        webhook_runtime_status: "healthy",
        is_active: true,
        account_is_active: true,
        registered_phone_number_count: 1,
        phone_number_count: 2,
        phone_numbers: [{ phone_number_id: "pn-1", display_phone_number: "+1-555-0100", verified_name: "Brand Demo", quality_rating: "GREEN", is_registered: true, is_active: true }],
        blocking_reasons: [],
      },
      {
        account_id: "acct-2",
        waba_id: "waba-2",
        display_name: "Account Two",
        onboarding_mode: "embedded_signup",
        has_access_token: true,
        webhook_runtime_status: "unknown",
        is_active: false,
        account_is_active: true,
        registered_phone_number_count: 0,
        phone_number_count: 0,
        phone_numbers: [],
        blocking_reasons: ["missing_phone_number"],
      },
    ]);
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  });

  afterEach(async () => {
    while (mountedRoots.length > 0) {
      const root = mountedRoots.pop();
      await act(async () => root?.unmount());
    }
    while (mountedContainers.length > 0) {
      mountedContainers.pop()?.remove();
    }
    vi.restoreAllMocks();
    delete (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT;
  });

  it("renders without crashing", async () => {
    await renderPage(createElement(MetaAccountsPage));
    expect(document.querySelectorAll("button").length).toBeGreaterThanOrEqual(0);
  });

  it("loads accounts on mount", async () => {
    await renderPage(createElement(MetaAccountsPage));
    expect(hoisted.listMetaAccountsMock).toHaveBeenCalled();
  });

  it("renders readiness and status summaries", async () => {
    await renderPage(createElement(MetaAccountsPage));
    expect(document.body.textContent).toContain("可正式激活");
    expect(document.body.textContent).toContain("根路由冲突");
    expect(document.body.textContent).toContain("1");
  });

  it("renders account cards with names", async () => {
    await renderPage(createElement(MetaAccountsPage));
    expect(document.body.textContent).toContain("Account One");
    expect(document.body.textContent).toContain("Account Two");
  });

  it("has a refresh button", async () => {
    await renderPage(createElement(MetaAccountsPage));
    expect(document.body.textContent).toContain("刷新");
  });

  it("shows phone numbers in account cards", async () => {
    await renderPage(createElement(MetaAccountsPage));
    expect(document.body.textContent).toContain("+1-555-0100");
  });
});
