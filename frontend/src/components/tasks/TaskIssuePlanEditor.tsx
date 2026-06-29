import type { ReactElement } from "react";
import { Button, Select, Space, Table, Typography } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import type { TableProps } from "antd";

import type { TaskIssuePlan } from "../../services/api";

type AccountOption = { label: string; value: string };

type TaskIssuePlanEditorProps = {
  accountOptions: AccountOption[];
  filterAccount?: string;
  onFilterAccountChange: (value: string | undefined) => void;
  onCreate: () => void;
  error?: string | null;
  plans: TaskIssuePlan[];
  columns: TableProps<TaskIssuePlan>["columns"];
  loading?: boolean;
};

export function TaskIssuePlanEditor({
  accountOptions,
  filterAccount,
  onFilterAccountChange,
  onCreate,
  error,
  plans,
  columns,
  loading = false,
}: TaskIssuePlanEditorProps): ReactElement {
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
          New Issue Plan
        </Button>
      </Space>
      {error ? <Typography.Text type="danger" style={{ display: "block", marginBottom: 8 }}>{error}</Typography.Text> : null}
      <Table
        dataSource={plans}
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
