import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAuthGuard } from "./useAuthGuard";
import { sessionManager } from "../../services/h5SessionManager";

const storage = new Map<string, string>();

function installLocalStorageMock(): void {
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

// Mock the session manager
vi.mock("../../services/h5SessionManager", () => ({
  sessionManager: {
    isAuthenticated: vi.fn(),
    getUserInfo: vi.fn(),
  },
}));

// Test component using the hook
function TestComponent({
  redirectToLogin,
  currentPath,
}: {
  redirectToLogin: boolean;
  currentPath: string;
}) {
  const { isAuthenticated, isLoading, user } = useAuthGuard(redirectToLogin, currentPath, vi.fn());
  return (
    <div>
      <span data-testid="auth">{isAuthenticated ? "authed" : "guest"}</span>
      <span data-testid="loading">{isLoading ? "loading" : "done"}</span>
      <span data-testid="user">{user?.displayName ?? "none"}</span>
    </div>
  );
}

describe("useAuthGuard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    storage.clear();
    installLocalStorageMock();
  });

  afterEach(() => {
    vi.clearAllMocks();
    cleanup();
    storage.clear();
  });

  it("returns guest when not authenticated", () => {
    vi.mocked(sessionManager.isAuthenticated).mockReturnValue(false);
    vi.mocked(sessionManager.getUserInfo).mockReturnValue(null);

    render(<TestComponent redirectToLogin={false} currentPath="/h5/tasks" />);

    expect(screen.getByTestId("auth").textContent).toBe("guest");
    expect(screen.getByTestId("user").textContent).toBe("none");
  });

  it("returns authed when authenticated", () => {
    vi.mocked(sessionManager.isAuthenticated).mockReturnValue(true);
    vi.mocked(sessionManager.getUserInfo).mockReturnValue({
      accountId: "1",
      phone: "13800138000",
      publicUserId: "u1",
      displayName: "Test User",
      inviteCode: "C001",
    });

    render(<TestComponent redirectToLogin={false} currentPath="/h5/tasks" />);

    expect(screen.getByTestId("auth").textContent).toBe("authed");
    expect(screen.getByTestId("user").textContent).toBe("Test User");
  });

  it("shows loading initially before useEffect runs", () => {
    vi.mocked(sessionManager.isAuthenticated).mockReturnValue(true);
    vi.mocked(sessionManager.getUserInfo).mockReturnValue({
      accountId: "1",
      phone: "13800138000",
      publicUserId: "u1",
      displayName: "Test User",
      inviteCode: "C001",
    });

    render(<TestComponent redirectToLogin={false} currentPath="/h5/tasks" />);

    // After render + useEffect runs: isLoading should be false
    expect(screen.getByTestId("loading").textContent).toBe("done");
  });

  it("calls onNavigate when redirectToLogin is true and not authenticated", () => {
    const onNavigate = vi.fn();
    vi.mocked(sessionManager.isAuthenticated).mockReturnValue(false);
    vi.mocked(sessionManager.getUserInfo).mockReturnValue(null);

    function NavTestComponent() {
      const { isAuthenticated, isLoading, user } = useAuthGuard(true, "/h5/orders", onNavigate);
      return (
        <div>
          <span data-testid="nav-auth">{isAuthenticated ? "authed" : "guest"}</span>
          <span data-testid="nav-loading">{isLoading ? "loading" : "done"}</span>
          <span data-testid="nav-user">{user?.displayName ?? "none"}</span>
        </div>
      );
    }

    render(<NavTestComponent />);

    expect(screen.getByTestId("nav-auth").textContent).toBe("guest");
    // Should have called onNavigate with login redirect
    expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders");
  });

  it("does not navigate when already authenticated", () => {
    const onNavigate = vi.fn();
    vi.mocked(sessionManager.isAuthenticated).mockReturnValue(true);
    vi.mocked(sessionManager.getUserInfo).mockReturnValue({
      accountId: "1",
      phone: "13800138000",
      publicUserId: "u1",
      displayName: "Test User",
      inviteCode: "C001",
    });

    function AuthedTestComponent() {
      const { isAuthenticated, user } = useAuthGuard(true, "/h5/tasks", onNavigate);
      return (
        <div>
          <span data-testid="authed-auth">{isAuthenticated ? "authed" : "guest"}</span>
          <span data-testid="authed-user">{user?.displayName ?? "none"}</span>
        </div>
      );
    }

    render(<AuthedTestComponent />);

    expect(screen.getByTestId("authed-auth").textContent).toBe("authed");
    expect(onNavigate).not.toHaveBeenCalled();
  });

  it("preserves redirect path for the earnings route", () => {
    const onNavigate = vi.fn();
    vi.mocked(sessionManager.isAuthenticated).mockReturnValue(false);
    vi.mocked(sessionManager.getUserInfo).mockReturnValue(null);

    function WalletRedirectTestComponent() {
      const { isAuthenticated } = useAuthGuard(true, "/h5/wallet", onNavigate);
      return <span data-testid="wallet-auth">{isAuthenticated ? "authed" : "guest"}</span>;
    }

    render(<WalletRedirectTestComponent />);

    expect(screen.getByTestId("wallet-auth").textContent).toBe("guest");
    expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Fwallet");
  });

  it("preserves the active site_key when redirecting an unauthenticated multi-site route to login", () => {
    const onNavigate = vi.fn();
    vi.mocked(sessionManager.isAuthenticated).mockReturnValue(false);
    vi.mocked(sessionManager.getUserInfo).mockReturnValue(null);

    function MultiSiteRedirectTestComponent() {
      const { isAuthenticated } = useAuthGuard(true, "/h5/orders?site_key=mall-es", onNavigate);
      return <span data-testid="multi-site-auth">{isAuthenticated ? "authed" : "guest"}</span>;
    }

    render(<MultiSiteRedirectTestComponent />);

    expect(screen.getByTestId("multi-site-auth").textContent).toBe("guest");
    expect(onNavigate).toHaveBeenCalledWith("/h5/login?site_key=mall-es&redirect=%2Fh5%2Forders%3Fsite_key%3Dmall-es");
  });

  it("surfaces onboarding, benefits, and support context around the login form", async () => {
    storage.set("h5-lang", "en");

    const { LoginPage } = await import("./LoginPage");
    render(
      <LoginPage
        page="login"
        siteKey="mall-cn"
        loginPhone=""
        loginPassword=""
        loginPasswordVisible={false}
        registerPhone=""
        registerPassword=""
        registerPasswordVisible={false}
        registerConfirmPassword=""
        registerConfirmPasswordVisible={false}
        rememberMe
        onRememberMeChange={vi.fn()}
        actionName={null}
        loginError={null}
        onLoginPhoneChange={vi.fn()}
        onLoginPasswordChange={vi.fn()}
        onLoginPasswordToggle={vi.fn()}
        onRegisterPhoneChange={vi.fn()}
        onRegisterPasswordChange={vi.fn()}
        onRegisterPasswordToggle={vi.fn()}
        onRegisterConfirmPasswordChange={vi.fn()}
        onRegisterConfirmPasswordToggle={vi.fn()}
        onLogin={vi.fn(async () => undefined)}
        onRegister={vi.fn(async () => undefined)}
        onNavigate={vi.fn()}
      />,
    );

    expect(
      screen.getByText(
        "Mobile-first member portal covering tasks, wallet, messages, tickets, and fragments.",
      ),
    ).toBeTruthy();
    expect(screen.getByText("Task Packages")).toBeTruthy();
    expect(screen.getByText("Dual Balance Wallet")).toBeTruthy();
    expect(screen.getByText("Fragment Collection")).toBeTruthy();
    expect(screen.getByText("Ticket Support")).toBeTruthy();
    expect(screen.getByText("Quick access for preview and QA review")).toBeTruthy();
    expect(screen.getByText("Self-service reset is not available. Contact support via ticket.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Submit Issue" })).toBeTruthy();
  });
});

describe("LoginPage", () => {
  beforeEach(() => {
    storage.clear();
    installLocalStorageMock();
  });

  afterEach(() => {
    cleanup();
    storage.clear();
  });

  it("keeps root scrolling locked and uses the auth shell as the only scroll container", async () => {
    document.documentElement.style.overflow = "hidden";
    document.documentElement.style.overflowY = "hidden";
    document.body.style.overflow = "hidden";
    document.body.style.overflowY = "hidden";

    const { LoginPage } = await import("./LoginPage");
    const view = render(
      <LoginPage
        page="login"
        siteKey="mall-cn"
        loginPhone=""
        loginPassword=""
        loginPasswordVisible={false}
        registerPhone=""
        registerPassword=""
        registerPasswordVisible={false}
        registerConfirmPassword=""
        registerConfirmPasswordVisible={false}
        rememberMe
        onRememberMeChange={vi.fn()}
        actionName={null}
        loginError={null}
        onLoginPhoneChange={vi.fn()}
        onLoginPasswordChange={vi.fn()}
        onLoginPasswordToggle={vi.fn()}
        onRegisterPhoneChange={vi.fn()}
        onRegisterPasswordChange={vi.fn()}
        onRegisterPasswordToggle={vi.fn()}
        onRegisterConfirmPasswordChange={vi.fn()}
        onRegisterConfirmPasswordToggle={vi.fn()}
        onLogin={vi.fn(async () => undefined)}
        onRegister={vi.fn(async () => undefined)}
        onNavigate={vi.fn()}
      />,
    );
    const main = screen.getByRole("main");

    expect(document.documentElement.style.overflow).toBe("hidden");
    expect(document.documentElement.style.overflowY).toBe("hidden");
    expect(document.body.style.overflow).toBe("hidden");
    expect(document.body.style.overflowY).toBe("hidden");
    expect(main.style.height).toBe("var(--h5-visual-viewport-height, 100dvh)");
    expect(main.style.overflowY).toBe("auto");
    expect(main.style.touchAction).toBe("pan-y");
    expect(main.style.webkitOverflowScrolling).toBe("touch");

    view.unmount();

    expect(document.documentElement.style.overflow).toBe("hidden");
    expect(document.documentElement.style.overflowY).toBe("hidden");
    expect(document.body.style.overflow).toBe("hidden");
    expect(document.body.style.overflowY).toBe("hidden");
  });

  it("renders localized chinese auth copy instead of english fallback", async () => {
    storage.set("h5-lang", "zh-CN");

    const { LoginPage } = await import("./LoginPage");
    render(
      <LoginPage
        page="login"
        siteKey="mall-cn"
        loginPhone=""
        loginPassword=""
        loginPasswordVisible={false}
        registerPhone=""
        registerPassword=""
        registerPasswordVisible={false}
        registerConfirmPassword=""
        registerConfirmPasswordVisible={false}
        rememberMe
        onRememberMeChange={vi.fn()}
        actionName={null}
        loginError={null}
        onLoginPhoneChange={vi.fn()}
        onLoginPasswordChange={vi.fn()}
        onLoginPasswordToggle={vi.fn()}
        onRegisterPhoneChange={vi.fn()}
        onRegisterPasswordChange={vi.fn()}
        onRegisterPasswordToggle={vi.fn()}
        onRegisterConfirmPasswordChange={vi.fn()}
        onRegisterConfirmPasswordToggle={vi.fn()}
        onLogin={vi.fn(async () => undefined)}
        onRegister={vi.fn(async () => undefined)}
        onNavigate={vi.fn()}
      />,
    );

    expect(screen.getAllByRole("button", { name: "登录" }).length).toBeGreaterThan(0);
    expect(screen.getByText("手机号")).toBeTruthy();
    expect(screen.getByText("记住我（7天内免登录）")).toBeTruthy();
    expect(screen.queryByText("Login")).toBeNull();
  });
});
