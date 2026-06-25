import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DetailTab } from "./DetailTab";

vi.mock("../../components/member/MemberIdLink", async () => {
  const React = await import("react");
  return {
    MemberIdLink: ({
      accountId,
      userId,
      publicUserId,
      label,
    }: {
      accountId?: string | null;
      userId?: string | null;
      publicUserId?: string | null;
      label?: string | null;
    }) =>
      React.createElement(
        "span",
        null,
        `member-link:${label ?? ""}:${userId ?? ""}:${publicUserId ?? ""}:${accountId ?? ""}`,
      ),
  };
});

vi.mock("antd", async () => {
  const React = await import("react");
  const Wrapper = ({ children }: { children?: React.ReactNode }) => React.createElement("div", null, children);
  const Descriptions = ({ children }: { children?: React.ReactNode }) => React.createElement("div", null, children);
  Descriptions.Item = ({
    label,
    children,
  }: {
    label?: React.ReactNode;
    children?: React.ReactNode;
  }) => React.createElement("div", null, label, children);
  return {
    Descriptions,
    Tag: Wrapper,
    Typography: { Text: Wrapper },
  };
});

describe("DetailTab", () => {
  it("renders customer id via MemberIdLink", () => {
    render(
      <DetailTab
        conversation={{
          account_id: "acct-1",
          customer_id: "user-1",
          customer_public_user_id: "pub-u1",
          management_mode: "ai_managed",
          status: "open",
          phone_number_id: "phone-1",
          last_message_at: "2026-06-24T00:00:00Z",
          latest_handover_recommended: false,
          latest_handover_reason: null,
          assigned_agent_name: null,
          assigned_agent_id: null,
        } as never}
        aiStatus={null}
      />,
    );

    expect(screen.getByText("member-link:pub-u1:user-1:pub-u1:acct-1")).toBeTruthy();
  });
});
