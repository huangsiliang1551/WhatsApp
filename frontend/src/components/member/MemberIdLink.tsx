import { Button, Typography } from "antd";
import type { JSX } from "react";

import { useAppStore } from "../../stores/appStore";
import { MemberProfilePopover } from "./MemberProfilePopover";

interface MemberIdLinkProps {
  accountId?: string | null;
  userId?: string | null;
  publicUserId?: string | null;
  label?: string | null;
}

export function MemberIdLink(props: MemberIdLinkProps): JSX.Element {
  const openCustomersPage = useAppStore((state) => state.openCustomersPage);
  const userId = props.userId?.trim() ?? "";
  const publicUserId = props.publicUserId?.trim() ?? "";
  const query = publicUserId || userId;
  const label = props.label?.trim() || publicUserId || userId;

  if (!query) {
    return <Typography.Text type="secondary">-</Typography.Text>;
  }

  const trigger = (
    <Button
      type="link"
      size="small"
      style={{ paddingInline: 0 }}
      onClick={() =>
        openCustomersPage({
          account_id: props.accountId ?? undefined,
          query,
          selected_profile_id: userId || undefined,
        })
      }
    >
      {label}
    </Button>
  );

  if (!userId) {
    return trigger;
  }

  return (
    <MemberProfilePopover accountId={props.accountId} publicUserId={props.publicUserId} userId={userId}>
      {trigger}
    </MemberProfilePopover>
  );
}
