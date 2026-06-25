import { Descriptions, Empty, Popover, Space, Spin, Tag, Typography } from "antd";
import { useEffect, useState, type JSX, type ReactNode } from "react";

import { usePermissions } from "../../hooks/usePermissions";
import { getMemberSummary } from "../../services/memberApi";
import type { CustomerSummaryResponse } from "../../types/member";

interface MemberProfilePopoverProps {
  accountId?: string | null;
  publicUserId?: string | null;
  userId: string;
  children: ReactNode;
}

function formatMoney(value: number | undefined): string {
  return Number(value ?? 0).toFixed(2);
}

export function MemberProfilePopover(props: MemberProfilePopoverProps): JSX.Element {
  const { can } = usePermissions();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [summary, setSummary] = useState<CustomerSummaryResponse | null>(null);
  const [loadedUserId, setLoadedUserId] = useState<string | null>(null);
  const canViewPopover = can("member.popover.view") || can("customers.detail");
  const canViewFinanceBreakdown = can("member.finance_breakdown.view") || can("customers.finance");

  useEffect(() => {
    if (!canViewPopover || !open || !props.userId || loadedUserId === props.userId) {
      return;
    }

    let active = true;
    setLoading(true);
    getMemberSummary(props.userId, props.accountId ?? undefined)
      .then((response) => {
        if (!active) return;
        setSummary(response);
        setLoadedUserId(props.userId);
      })
      .catch(() => {
        if (!active) return;
        setSummary(null);
        setLoadedUserId(props.userId);
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [canViewPopover, open, props.userId, props.accountId, loadedUserId]);

  useEffect(() => {
    setSummary(null);
    setLoadedUserId(null);
    setOpen(false);
  }, [props.userId, props.accountId]);

  const content = loading ? (
    <div style={{ width: 280, padding: "12px 0", textAlign: "center" }}>
      <Spin size="small" />
    </div>
  ) : summary ? (
    <Space direction="vertical" size={10} style={{ width: 300 }}>
      <div>
        <Typography.Text strong>{summary.customer.display_name || summary.customer.public_user_id}</Typography.Text>
        <div>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {summary.customer.public_user_id}
          </Typography.Text>
        </div>
      </div>
      <Descriptions
        size="small"
        column={1}
        items={[
          {
            key: "lifecycle",
            label: "状态",
            children: <Tag color={summary.customer.lifecycle_status === "active" ? "green" : "default"}>{summary.customer.lifecycle_status}</Tag>,
          },
          {
            key: "balance",
            label: "系统余额",
            children: canViewFinanceBreakdown ? formatMoney(summary.wallet.balance) : "需财务权限",
          },
          {
            key: "recharged",
            label: "累计充值",
            children: canViewFinanceBreakdown ? formatMoney(summary.wallet.total_recharged) : "需财务权限",
          },
          {
            key: "withdrawn",
            label: "累计提现",
            children: canViewFinanceBreakdown ? formatMoney(summary.wallet.total_withdrawn) : "需财务权限",
          },
          {
            key: "verification",
            label: "实名",
            children: summary.member_status.verification.status,
          },
          {
            key: "binding",
            label: "WhatsApp",
            children: summary.member_status.whatsapp_binding.status,
          },
          {
            key: "conversations",
            label: "会话",
            children: `${summary.conversations.total} / open ${summary.conversations.open}`,
          },
          {
            key: "tickets",
            label: "工单",
            children: `${summary.tickets.total} / open ${summary.tickets.open}`,
          },
        ]}
      />
      {summary.tags.length > 0 ? (
        <Space wrap size={[4, 4]}>
          {summary.tags.map((tag) => (
            <Tag key={tag}>{tag.toUpperCase()}</Tag>
          ))}
        </Space>
      ) : null}
    </Space>
  ) : (
    <div style={{ width: 280 }}>
      <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无会员摘要" />
    </div>
  );

  if (!canViewPopover) {
    return <>{props.children}</>;
  }

  return (
    <Popover content={content} destroyOnHidden open={open} placement="rightTop">
      <span
        onBlur={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
      >
        {props.children}
      </span>
    </Popover>
  );
}
