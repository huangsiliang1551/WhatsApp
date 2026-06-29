import type { ReactElement } from "react";
import { Button, Select, Space, Table, Typography } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import type { TableProps } from "antd";

import type { TaskQuota } from "../../services/api";

type AccountOption = { label: string; value: string };

type MemberTaskQuotaPanelProps = {
  accountOptions: AccountOption[];
  filterAccount?: string;
  onFilterAccountChange: (value: string | undefined) => void;
  onCreate: () => void;
  onBatchCreate?: () => void;
  error?: string | null;
  quotas: TaskQuota[];
  columns: TableProps<TaskQuota>["columns"];
  loading?: boolean;
};

export function MemberTaskQuotaPanel({
  accountOptions,
  filterAccount,
  onFilterAccountChange,
  onCreate,
  onBatchCreate,
  error,
  quotas,
  columns,
  loading = false,
}: MemberTaskQuotaPanelProps): ReactElement {
  return (
    <div>
      <Space style={{ marginBottom: 12 }} wrap>
        <Select
          placeholder="Filter Account"
          allowClear
          style={{ width: 160 }}
          value={filterAccount}
          onChange={onFilterAccountChange}
          options={accountOptions}
        />
        <Button size="small" type="primary" icon={<PlusOutlined />} onClick={onCreate}>
          New Quota
        </Button>
        {onBatchCreate ? (
          <Button size="small" onClick={onBatchCreate}>
            Batch Create
          </Button>
        ) : null}
      </Space>
      {error ? <Typography.Text type="danger" style={{ display: "block", marginBottom: 8 }}>{error}</Typography.Text> : null}
      <Table
        dataSource={quotas}
        columns={columns}
        rowKey="id"
        size="small"
        loading={loading}
        pagination={{ pageSize: 20, showSizeChanger: true }}
        scroll={{ y: "calc(100vh - 440px)" }}
      />
    </div>
  );
}
