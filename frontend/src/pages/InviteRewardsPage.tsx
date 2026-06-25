import { Button, Select, Space, Table, Tag, Typography, type TableColumnsType } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import { useCallback, useMemo, useState, type JSX } from "react";

import { MemberIdLink } from "../components/member/MemberIdLink";
import { PageShell } from "../components/PageShell";
import { usePageData } from "../hooks/usePageData";
import { listInviteRewards, type InviteAdminRecord } from "../services/marketingApi";
import { useAppStore } from "../stores/appStore";

export function InviteRewardsPage(): JSX.Element {
  const actorAccountIds = useAppStore((state) => state.actorAccountIds);
  const defaultAccountId = actorAccountIds.length > 0 ? actorAccountIds[0] : undefined;
  const [rewardedFilter, setRewardedFilter] = useState<boolean | undefined>(undefined);

  const fetcher = useCallback(async () => {
    return listInviteRewards({
      account_id: defaultAccountId,
      is_rewarded: rewardedFilter,
      page: 1,
      size: 100,
    });
  }, [defaultAccountId, rewardedFilter]);

  const { data, loading, error, reload } = usePageData({ fetcher });
  const rows = data?.items ?? [];

  const columns = useMemo<TableColumnsType<InviteAdminRecord>>(
    () => [
      {
        title: "邀请人 ID",
        key: "inviter",
        render: (_, record) => (
          <MemberIdLink
            accountId={record.account_id}
            userId={record.inviter_user_id}
            publicUserId={record.inviter_public_user_id}
            label={record.inviter_public_user_id}
          />
        ),
      },
      {
        title: "被邀请人 ID",
        key: "invitee",
        render: (_, record) => (
          <MemberIdLink
            accountId={record.account_id}
            userId={record.invitee_user_id}
            publicUserId={record.invitee_public_user_id}
            label={record.invitee_public_user_id}
          />
        ),
      },
      {
        title: "奖励金额",
        dataIndex: "reward_amount",
        key: "reward_amount",
        render: (value: string | number) => `￥${value}`,
      },
      {
        title: "资金口径",
        dataIndex: "reward_fund_type",
        key: "reward_fund_type",
        render: (value: string) => <Tag color="gold">{value}</Tag>,
      },
      {
        title: "流水类型",
        dataIndex: "reward_transaction_type",
        key: "reward_transaction_type",
      },
      {
        title: "入账状态",
        dataIndex: "is_rewarded",
        key: "is_rewarded",
        render: (value: boolean) => <Tag color={value ? "green" : "default"}>{value ? "已入账" : "未入账"}</Tag>,
      },
      {
        title: "创建时间",
        dataIndex: "created_at",
        key: "created_at",
        render: (value: string | null) => value ? new Date(value).toLocaleString("zh-CN") : "-",
      },
    ],
    []
  );

  const actions = (
    <Space>
      <Select
        allowClear
        placeholder="入账状态"
        value={rewardedFilter}
        onChange={(value) => setRewardedFilter(value)}
        options={[
          { label: "已入账", value: true },
          { label: "未入账", value: false },
        ]}
        style={{ width: 140 }}
      />
      <Button size="small" icon={<ReloadOutlined />} onClick={() => void reload()} loading={loading}>
        刷新
      </Button>
    </Space>
  );

  return (
    <PageShell title="邀请奖励流水" subtitle="查看邀请奖励金额、入账状态和当前资金口径" actions={actions}>
      <AlertBanner />
      {error ? (
        <Typography.Text type="danger" style={{ display: "block", marginBottom: 12 }}>
          {error}
        </Typography.Text>
      ) : null}
      <Table rowKey="id" dataSource={rows} columns={columns} loading={loading} pagination={{ pageSize: 20 }} />
    </PageShell>
  );
}

function AlertBanner(): JSX.Element {
  return (
    <Typography.Paragraph type="secondary" style={{ marginBottom: 12 }}>
      当前页面展示的是邀请奖励记录及其入账状态。现阶段资金口径仍按后端返回值展示，便于后续继续收口到赠金/任务奖励统一账务模型。
    </Typography.Paragraph>
  );
}
