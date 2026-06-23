import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LoginPage } from "./LoginPage";

const hoisted = vi.hoisted(() => ({
  loginMock: vi.fn<() => Promise<{ access_token: string; refresh_token: string }>>(),
  getMeMock: vi.fn<() => Promise<{ id: string; username: string; display_name: string; role: string }>>(),
  isAuthenticatedMock: vi.fn<() => boolean>(),
  getAccessTokenMock: vi.fn<() => string | null>(),
}));

vi.mock("../services/adminAuth", () => ({
  adminAuth: {
    login: hoisted.loginMock,
    getMe: hoisted.getMeMock,
    isAuthenticated: hoisted.isAuthenticatedMock,
    getAccessToken: hoisted.getAccessTokenMock,
  },
}));

vi.mock("antd", async () => {
  const React = await import("react");
  const Wrapper = ({ children }: { children?: React.ReactNode }) =>
    React.createElement("div", null, children);
  const Button = ({ children, onClick, htmlType, disabled, loading }: { children?: React.ReactNode; onClick?: () => void; htmlType?: string; disabled?: boolean; loading?: boolean }) =>
    React.createElement("button", { onClick, disabled: disabled || loading, type: htmlType, "data-loading": loading ? "true" : undefined }, children);
  const Input = ({ prefix, placeholder, autoFocus }: { prefix?: React.ReactNode; placeholder?: string; autoFocus?: boolean }) =>
    React.createElement("input", { placeholder, autoFocus });
  (Input as unknown as Record<string, unknown>).Password = ({ prefix, placeholder }: { prefix?: React.ReactNode; placeholder?: string }) =>
    React.createElement("input", { placeholder, type: "password" });
  const Checkbox = ({ children }: { children?: React.ReactNode }) =>
    React.createElement("label", null, children);
  const Card = ({ children, style }: { children?: React.ReactNode; style?: Record<string, unknown> }) =>
    React.createElement("div", { style }, children);
  const Form = ({ children, onFinish, layout, size }: { children?: React.ReactNode; onFinish?: (values: unknown) => void; layout?: string; size?: string }) =>
    React.createElement("form", { onSubmit: (e: Event) => { e.preventDefault(); onFinish?.({}); } }, children);
  const Typography = { Title: ({ children }: { children?: React.ReactNode }) => React.createElement("h1", null, children), Text: ({ children }: { children?: React.ReactNode }) => React.createElement("span", null, children), Paragraph: ({ children }: { children?: React.ReactNode }) => React.createElement("p", null, children) };
  Form.Item = ({ children, name, rules }: { children?: React.ReactNode; name?: string; rules?: Array<{ required?: boolean; message?: string }> }) => React.createElement("div", null, children);
  Form.useForm = () => [{ getFieldsValue: () => ({}) }];
  const message = { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn(), loading: vi.fn() };
  return { Button, Input, Checkbox, Card, Form, Typography, message, ConfigProvider: Wrapper, App: Wrapper };
});

vi.mock("@ant-design/icons", () => ({
  UserOutlined: () => null,
  LockOutlined: () => null,
}));

vi.mock("../stores/appStore", () => ({
  useAppStore: (selector: (s: Record<string, unknown>) => unknown) =>
    selector({
      setConsoleAgentId: vi.fn(),
      setConsoleAgentName: vi.fn(),
      setActorRole: vi.fn(),
      setActorAccountIds: vi.fn(),
    }),
}));

describe("LoginPage", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    hoisted.loginMock.mockResolvedValue({ access_token: "test-token", refresh_token: "test-refresh" });
    hoisted.getMeMock.mockResolvedValue({ id: "admin-1", username: "admin", display_name: "管理员", role: "admin" });
    hoisted.isAuthenticatedMock.mockReturnValue(false);
  });

  afterEach(() => {
    act(() => root.unmount());
    document.body.removeChild(container);
  });

  it("renders without crashing", () => {
    act(() => { root.render(<LoginPage />); });
    expect(container.textContent).toContain("管理后台");
  });

  it("renders login form with username and password fields", () => {
    act(() => { root.render(<LoginPage />); });
    expect(container.innerHTML).toContain("input");
  });

  it("shows login button", () => {
    act(() => { root.render(<LoginPage />); });
    const buttons = container.querySelectorAll("button");
    expect(buttons.length).toBeGreaterThanOrEqual(1);
  });
});
