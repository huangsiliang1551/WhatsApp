import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAuthGuard } from "./useAuthGuard";
import { getCurrentMemberSession } from "../../services/h5Member";

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

vi.mock("../../services/h5Member", () => ({
  getCurrentMemberSession: vi.fn(),
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

  it("returns guest when not authenticated", async () => {
    vi.mocked(getCurrentMemberSession).mockResolvedValue(null);

    render(<TestComponent redirectToLogin={false} currentPath="/h5/tasks" />);

    await waitFor(() => expect(screen.getByTestId("loading").textContent).toBe("done"));
    expect(screen.getByTestId("auth").textContent).toBe("guest");
    expect(screen.getByTestId("user").textContent).toBe("none");
  });

  it("returns authed when authenticated", async () => {
    vi.mocked(getCurrentMemberSession).mockResolvedValue({
      accountId: "1",
      phone: "13800138000",
      publicUserId: "u1",
      displayName: "Test User",
      inviteCode: "C001",
    });

    render(<TestComponent redirectToLogin={false} currentPath="/h5/tasks" />);

    await waitFor(() => expect(screen.getByTestId("auth").textContent).toBe("authed"));
    expect(screen.getByTestId("user").textContent).toBe("Test User");
  });

  it("shows loading initially before useEffect runs", async () => {
    vi.mocked(getCurrentMemberSession).mockResolvedValue({
      accountId: "1",
      phone: "13800138000",
      publicUserId: "u1",
      displayName: "Test User",
      inviteCode: "C001",
    });

    render(<TestComponent redirectToLogin={false} currentPath="/h5/tasks" />);

    expect(screen.getByTestId("loading").textContent).toBe("loading");
    await waitFor(() => expect(screen.getByTestId("loading").textContent).toBe("done"));
  });

  it("calls onNavigate when redirectToLogin is true and not authenticated", async () => {
    const onNavigate = vi.fn();
    vi.mocked(getCurrentMemberSession).mockResolvedValue(null);

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

    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Forders"));
