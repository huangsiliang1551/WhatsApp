import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TaskRulesPage } from "./TaskRulesPage";

const hoisted = vi.hoisted(() => ({
  storeState: {
    actorAccountIds: ["acct-1"],
  } as Record<string, unknown>,
  listPackagesMock: vi.fn(),
  listTaskRulesMock: vi.fn(),
  createTaskRuleMock: vi.fn(),
  updateTaskRuleMock: vi.fn(),
  deleteTaskRuleMock: vi.fn(),
  toggleTaskRuleMock: vi.fn(),
  getSignInConfigMock: vi.fn(),
  updateSignInConfigMock: vi.fn(),
  getMarketingStatsMock: vi.fn(),
  listTaskIssuePlansMock: vi.fn(),
  getTaskSystemConfigMock: vi.fn(),
}));

vi.mock("../services/marketingApi", () => ({
  listPackages: hoisted.listPackagesMock,
  listTaskRules: hoisted.listTaskRulesMock,
  createTaskRule: hoisted.createTaskRuleMock,
  updateTaskRule: hoisted.updateTaskRuleMock,
  deleteTaskRule: hoisted.deleteTaskRuleMock,
  toggleTaskRule: hoisted.toggleTaskRuleMock,
  getSignInConfig: hoisted.getSignInConfigMock,
  updateSignInConfig: hoisted.updateSignInConfigMock,
  getMarketingStats: hoisted.getMarketingStatsMock,
}));

vi.mock("../services/api", () => ({
  listTaskIssuePlans: hoisted.listTaskIssuePlansMock,
  getTaskSystemConfig: hoisted.getTaskSystemConfigMock,
  patchTaskSystemConfig: vi.fn(),
}));

vi.mock("../stores/appStore", () => ({
  useAppStore: (selector: (state: Record<string, unknown>) => unknown) => selector(hoisted.storeState),
}));

vi.mock("../components/PageShell", () => ({
  PageShell: ({
    title,
    subtitle,
    actions,
    children,
  }: {
    title?: string;
    subtitle?: string;
    actions?: React.ReactNode;
    children?: React.ReactNode;
  }) => createElement("section", null, createElement("h1", null, title), createElement("p", null, subtitle), actions, children),
}));

vi.mock("../components/Feedback", () => ({
  DangerButton: ({
    label,
    onConfirm,
  }: {
    label: string;
    onConfirm?: () => void;
  }) => createElement("button", { onClick: onConfirm, type: "button" }, label),
  showError: vi.fn(),
  showSuccess: vi.fn(),
}));

vi.mock("antd", async () => {
  const React = await import("react");
  const Wrapper = ({ children }: { children?: React.ReactNode }) => React.createElement("div", null, children);
  const Card = ({ title, children }: { title?: React.ReactNode; children?: React.ReactNode }) =>
    React.createElement("section", null, title ? React.createElement("h3", null, title) : null, children);
  const Button = ({
    children,
    onClick,
  }: {
    children?: React.ReactNode;
    onClick?: () => void;
  }) => React.createElement("button", { onClick }, children);
  const Select = ({ options = [], placeholder }: { options?: Array<{ label: string; value: string }>; placeholder?: string }) =>
    React.createElement(
      "select",
      { "aria-label": placeholder ?? "select" },
      options.map((option) => React.createElement("option", { key: option.value, value: option.value }, option.label)),
    );
  const Input = ({ placeholder }: { placeholder?: string }) => React.createElement("input", { placeholder });
  const InputNumber = ({ placeholder }: { placeholder?: string }) => React.createElement("input", { placeholder, type: "number" });
  const Checkbox = ({ children }: { children?: React.ReactNode }) =>
    React.createElement("input", { "aria-label": String(children ?? "checkbox"), type: "checkbox" });
  const Tabs = ({
    items = [],
    activeKey,
    onChange,
  }: {
    items?: Array<{ key: string; label: React.ReactNode; children: React.ReactNode }>;
    activeKey?: string;
    onChange?: (key: string) => void;
  }) =>
    React.createElement(
      "div",
      null,
      React.createElement(
        "div",
        null,
        items.map((item) =>
          React.createElement(
            "button",
            {
              key: item.key,
              onClick: () => onChange?.(item.key),
              type: "button",
            },
            item.label,
          ),
        ),
      ),
      items.find((item) => item.key === activeKey)?.children ?? null,
    );
  const Form = Wrapper as typeof Wrapper & { useForm: () => Array<Record<string, unknown>>; Item?: typeof Wrapper; List?: typeof Wrapper };
  Form.useForm = () => [
    {
      setFieldsValue: vi.fn(),
      resetFields: vi.fn(),
      submit: vi.fn(),
    },
  ];
  Form.Item = ({ label, children }: { label?: React.ReactNode; children?: React.ReactNode }) =>
    React.createElement("label", null, label, children);
  Form.List = ({ children }: { children?: React.ReactNode }) => React.createElement("div", null, typeof children === "function" ? null : children);

  return {
    Alert: Wrapper,
    Button,
    Card,
    Checkbox,
    Col: Wrapper,
    Form,
    Input,
    InputNumber,
    Modal: Wrapper,
    Row: Wrapper,
    Select,
    Space: Wrapper,
    Statistic: Wrapper,
    Table: Wrapper,
    Tabs,
    Tag: Wrapper,
    TimePicker: Wrapper,
    Typography: {
      Text: Wrapper,
    },
  };
});

describe("TaskRulesPage", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    hoisted.listPackagesMock.mockResolvedValue([]);
    hoisted.listTaskRulesMock.mockResolvedValue([]);
    hoisted.getSignInConfigMock.mockResolvedValue({
      consecutive_days: 3,
      reward_amount: 10,
    });
    hoisted.getMarketingStatsMock.mockResolvedValue({
      push_triggered: 0,
      push_claimed: 0,
      push_completed: 0,
      push_reward_total: 0,
      signin_count: 0,
      signin_completed: 0,
      signin_reward_total: 0,
      invite_share_count: 0,
      invite_registration: 0,
      invite_recharge: 0,
      invite_reward_total: 0,
      daily_trend: [],
    });
    hoisted.listTaskIssuePlansMock.mockResolvedValue([
      { id: "plan-newbie", name: "鏂版墜璁″垝", account_id: "acct-1", plan_type: "newbie", status: "active" },
      { id: "plan-official", name: "姝ｅ紡璁″垝", account_id: "acct-1", plan_type: "official", status: "active" },
    ]);
    hoisted.getTaskSystemConfigMock.mockResolvedValue({
      id: "cfg-1",
      accountId: "acct-1",
      siteId: null,
      status: "active",
      whatsappBindingRewardEnabled: true,
      whatsappBindingRewardAmount: "20.00",
      whatsappBindingRewardWalletType: "task_balance",
      whatsappBindingRewardCurrency: "USD",
      certifiedMemberEnabled: true,
      certifiedRechargeThreshold: "50.00",
      certifiedRechargeScope: "real_recharge",
      autoCertifyOnRecharge: true,
      newbieTaskEnabled: true,
      newbiePlanId: "plan-newbie",
      newbieAutoPopup: true,
      officialPlanId: "plan-official",
      showTaskBalanceTransferPrompt: true,
      minTaskBalanceTransferPromptAmount: "1.00",
      maxActiveBatchesPerUser: 1,
      maxActivePackagesPerUser: 1,
      metadataJson: null,
    });
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    delete (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT;
    vi.clearAllMocks();
  });

  it("adds a v3 basic settings tab and loads task system config data", async () => {
    await act(async () => {
      root.render(createElement(TaskRulesPage));
    });

    await waitFor(() => {
      expect(container.textContent).toContain("基础设置");
    });

    const basicTabButton = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent === "基础设置",
    );
    expect(basicTabButton).toBeTruthy();

    await act(async () => {
      basicTabButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    await waitFor(() => {
      expect(hoisted.getTaskSystemConfigMock).toHaveBeenCalledWith({
        account_id: "acct-1",
      });
      expect(hoisted.listTaskIssuePlansMock).toHaveBeenCalledWith({
        account_id: "acct-1",
      });
      expect(container.textContent).toContain("新手任务");
      expect(container.textContent).toContain("正式任务");
      expect(container.textContent).toContain("活跃批次上限");
    });
  });

  it("keeps legacy push, signin, and stats tabs while injecting the new v3 basic settings tab", async () => {
    await act(async () => {
      root.render(createElement(TaskRulesPage));
    });

    await waitFor(() => {
      const tabLabels = Array.from(container.querySelectorAll("button")).map((button) => button.textContent);
      expect(tabLabels).toContain("基础设置");
      expect(tabLabels).toContain("推送规则");
      expect(tabLabels).toContain("签到配置");
      expect(tabLabels).toContain("统计");
    });
  });
});
