import { Button, Input, Select, Space, Table, Tag, Typography, type TableColumnsType } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import { useCallback, useMemo, useState, type JSX } from "react";

import { MemberIdLink } from "../components/member/MemberIdLink";
import { PageShell } from "../components/PageShell";
import { usePageData } from "../hooks/usePageData";
import { listInviteRelations, type InviteAdminRecord } from "../services/marketingApi";
import { useAppStore } from "../stores/appStore";

export function InviteRelationsPage(): JSX.Element {
  const actorAccountIds = useAppStore((state) => state.actorAccountIds);
  const defaultAccountId = actorAccountIds.length > 0 ? actorAccountIds[0] : undefined;
  const [inviterQuery, setInviterQuery] = useState("");
  const [inviteeQuery, setInviteeQuery] = useState("");
  const [inviteType, setInviteType] = useState<string | undefined>(undefined);

  const fetcher = useCallback(async () => {
    return listInviteRelations({
      account_id: defaultAccountId,
      inviter_user_id: inviterQuery || undefined,
      invitee_user_id: inviteeQuery || undefined,
      invite_type: inviteType,
      page: 1,
      size: 100,
    });
  }, [defaultAccountId, inviterQuery, inviteeQuery, inviteType]);

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
        title: "邀请类型",
        dataIndex: "invite_type",
        key: "invite_type",
        render: (value: string) => <Tag color={value === "recharge" ? "blue" : "green"}>{value}</Tag>,
      },
      {
        title: "奖励状态",
        dataIndex: "is_rewarded",
        key: "is_rewarded",
        render: (value: boolean) => <Tag color={value ? "green" : "default"}>{value ? "已奖励" : "未奖励"}</Tag>,
      },
      {
        title: "风险线索",
        key: "risk",
        render: (_, record) => (
          <Typography.Text type={record.invitee_ip || record.invitee_device_id ? "warning" : "secondary"}>
            {record.invitee_ip || record.invitee_device_id ? "有 IP/设备线索" : "无"}
          </Typography.Text>
        ),
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
      <Input
        placeholder="邀请人 user_id"
        value={inviterQuery}
        onChange={(event) => setInviterQuery(event.target.value)}
        style={{ width: 180 }}
      />
      <Input
        placeholder="被邀请人 user_id"
        value={inviteeQuery}
        onChange={(event) => setInviteeQuery(event.target.value)}
        style={{ width: 180 }}
      />
      <Select
        allowClear
        placeholder="邀请类型"
        value={inviteType}
        onChange={(value) => setInviteType(value)}
        options={[
          { label: "注册", value: "register" },
          { label: "充值", value: "recharge" },
        ]}
        style={{ width: 140 }}
      />
      <Button size="small" icon={<ReloadOutlined />} onClick={() => void reload()} loading={loading}>
        刷新
      </Button>
    </Space>
  );

  return (
    <PageShell title="邀请关系" subtitle="查看邀请人、被邀请人、邀请类型和风险线索" actions={actions}>
      {error ? (
        <Typography.Text type="danger" style={{ display: "block", marginBottom: 12 }}>
          {error}
        </Typography.Text>
      ) : null}
      <Table rowKey="id" dataSource={rows} columns={columns} loading={loading} pagination={{ pageSize: 20 }} />
    </PageShell>
  );
}
