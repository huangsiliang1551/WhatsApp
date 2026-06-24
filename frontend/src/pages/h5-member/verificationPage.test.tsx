import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t } from "./i18n";
import { formatTimestamp } from "./sharedUtils";

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

type MockMediaUploaderProps = {
  onUpload: (files: Array<{ file: File }>) => void;
};

let latestMediaUploaderProps: MockMediaUploaderProps | null = null;

vi.mock("./MediaUploader", () => ({
  MediaUploader: (props: MockMediaUploaderProps) => {
    latestMediaUploaderProps = props;
    return (
      <button
        onClick={() =>
          props.onUpload([
            {
              file: new File(["verification"], "passport.png", {
                type: "image/png",
              }),
            },
          ])
        }
        type="button"
      >
        mock-upload
      </button>
    );
  },
}));

type VerificationPageProps = React.ComponentProps<
  typeof import("./VerificationPage").VerificationPage
>;

async function renderVerificationPage(
  overrides: Partial<VerificationPageProps> = {},
): Promise<{
  props: VerificationPageProps;
}> {
  const { VerificationPage } = await import("./VerificationPage");
  const props: VerificationPageProps = {
    effectiveVerificationSummary: {
      currentStatus: "under_review",
      hasActiveRequest: true,
      activeRequest: null,
      history: [],
    } as never,
    verificationRequests: [],
    verificationRequestDetail: null,
    verificationHistory: [
      {
        id: "vr-older",
        requestType: "identity",
        status: "approved",
        notes: "Older request",
        reviewNote: "Approved",
        createdAt: "2026-06-19T09:00:00.000Z",
        updatedAt: "2026-06-20T09:00:00.000Z",
        documents: [],
      },
      {
        id: "vr-latest",
        requestType: "identity",
        status: "under_review",
        notes: "Latest request",
        reviewNote: null,
        createdAt: "2026-06-21T09:00:00.000Z",
        updatedAt: "2026-06-23T15:30:00.000Z",
        documents: [{ id: "doc-1", fileName: "passport.png", storageKey: "uploads/passport.png", createdAt: "2026-06-23T15:31:00.000Z" }],
      },
    ] as never,
    verificationNotes: "",
    focusedVerificationRequest: null,
    canSubmitVerificationRequest: true,
    verificationActionId: null,
    siteKey: "mall-us",
    onNavigate: vi.fn(),
    onSubmitVerification: vi.fn().mockResolvedValue(undefined),
    onOpenVerificationRequest: vi.fn().mockResolvedValue(undefined),
    onVerificationNotesChange: vi.fn(),
    verificationName: "Alice Doe",
    verificationIdNumber: "P1234567",
    actionName: null,
    onSubmitVerificationApi: vi.fn().mockResolvedValue(undefined),
    onVerificationNameChange: vi.fn(),
    onVerificationIdNumberChange: vi.fn(),
    onVerificationPhotoFilesChange: vi.fn(),
    loading: false,
    ...overrides,
  };

  render(<VerificationPage {...props} />);
  return { props };
}

describe("VerificationPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    latestMediaUploaderProps = null;
    storage.clear();
    installLocalStorageMock();
    storage.set("h5-lang", "en-US");
  });

  afterEach(() => {
    vi.clearAllMocks();
    latestMediaUploaderProps = null;
    cleanup();
    storage.clear();
  });

  it("shows the latest history timestamp in the status card when no focused request is loaded", async () => {
    const latestUpdatedAt = formatTimestamp("2026-06-23T15:30:00.000Z");

    await renderVerificationPage();

    const lastUpdatedCard = screen.getByText(t("verification.lastUpdate")).closest(".h5-member-detail-card");
    expect(lastUpdatedCard).toBeTruthy();
    expect(within(lastUpdatedCard!).getByText(latestUpdatedAt)).toBeTruthy();
    expect(within(lastUpdatedCard!).queryByText(t("verification.noRecord"))).toBeNull();
  });

  it("fills the example note from the empty-state action", async () => {
    const onVerificationNotesChange = vi.fn();

    await renderVerificationPage({
      focusedVerificationRequest: null,
      onVerificationNotesChange,
    });

    fireEvent.click(screen.getByRole("button", { name: t("verification.fillExample") }));

    expect(onVerificationNotesChange).toHaveBeenCalledWith(t("verification.exampleNote"));
  });

  it("keeps submit disabled without a name and shows the submitting label during submit", async () => {
    await renderVerificationPage({
      verificationName: "",
    });

    expect((screen.getByRole("button", { name: t("verification.submitRequestBtn") }) as HTMLButtonElement).disabled).toBe(true);

    cleanup();

    await renderVerificationPage({
      actionName: "verification-api-submit",
    });

    expect((screen.getByRole("button", { name: t("verification.submitting") }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("forwards uploaded files to verification photo state", async () => {
    const onVerificationPhotoFilesChange = vi.fn();

    await renderVerificationPage({
      onVerificationPhotoFilesChange,
    });

    fireEvent.click(screen.getByRole("button", { name: t("verification.photoLabel") }));

    expect(latestMediaUploaderProps).toBeTruthy();
    expect(onVerificationPhotoFilesChange).toHaveBeenCalledTimes(1);
    const files = vi.mocked(onVerificationPhotoFilesChange).mock.calls[0]?.[0] as File[];
    expect(files).toHaveLength(1);
    expect(files[0]?.name).toBe("passport.png");
  });

  it("shows loading on the active history row and opens details when clicked", async () => {
    const onOpenVerificationRequest = vi.fn().mockResolvedValue(undefined);

    await renderVerificationPage({
      verificationActionId: "detail:vr-latest",
      onOpenVerificationRequest,
    });

    const activeHistoryRow = screen.getByText(t("verification.loading")).closest("button");
    expect(activeHistoryRow).toBeTruthy();

    fireEvent.click(activeHistoryRow!);

    expect(onOpenVerificationRequest).toHaveBeenCalledWith("vr-latest");
  });

  it("surfaces a preparation checklist before the submission form and history", async () => {
    await renderVerificationPage();

    const prepHeading = screen.getByText(t("verification.prepTitle"));
    const submitHeading = screen.getByText(t("verification.submitRequest"));
    const historyHeading = screen.getByText(t("verification.applicationHistory"));

    expect(prepHeading.compareDocumentPosition(submitHeading)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(submitHeading.compareDocumentPosition(historyHeading)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(screen.getByText(t("verification.prepIdentityTitle"))).toBeTruthy();
    expect(screen.getByText(t("verification.prepPhotoTitle"))).toBeTruthy();
    expect(screen.getByText(t("verification.prepReviewTitle"))).toBeTruthy();
  });

  it("opens support from the verification form when the member needs help", async () => {
    const onNavigate = vi.fn();

    await renderVerificationPage({
      onNavigate,
    });

    fireEvent.click(screen.getByRole("button", { name: t("verification.openSupport") }));

    expect(onNavigate).toHaveBeenCalledWith("/h5/tickets/new");
  });
});
