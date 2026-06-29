import type { ReactElement } from "react";
import { Modal, Space, Table, Typography } from "antd";
import type { TableProps } from "antd";

import type { TaskPackageAdminDetail } from "../../services/api";

type TaskInstanceDetailDrawerProps = {
  open: boolean;
  loading?: boolean;
  detail: TaskPackageAdminDetail | null;
  onClose: () => void;
  formatMoney: (value: number | string | null | undefined) => string;
  itemColumns: TableProps<Record<string, unknown>>["columns"];
  logColumns: TableProps<Record<string, unknown>>["columns"];
};

export function TaskInstanceDetailDrawer({
  open,
  loading = false,
  detail,
  onClose,
  formatMoney,
  itemColumns,
  logColumns,
}: TaskInstanceDetailDrawerProps): ReactElement {
  return (
    <Modal title="Package Detail" open={open} onCancel={onClose} footer={null}>
      {loading ? (
        <Typography.Text>Loading package detail...</Typography.Text>
      ) : detail ? (
        <Space direction="vertical" style={{ width: "100%" }} size={12}>
          <Typography.Text strong>{detail.id}</Typography.Text>
          <Typography.Text>Progress: {detail.progress_label}</Typography.Text>
          <Typography.Text>Day Planned Amount: {formatMoney(detail.day_planned_amount)}</Typography.Text>
          <Typography.Text>Day System Amount: {formatMoney(detail.day_system_generated_amount)}</Typography.Text>
          <Typography.Text>Day Manual Added Amount: {formatMoney(detail.day_manual_added_amount)}</Typography.Text>
          <Typography.Text>Day Effective Amount: {formatMoney(detail.day_effective_amount)}</Typography.Text>
          <Typography.Text>Package Planned Amount: {formatMoney(detail.planned_amount)}</Typography.Text>
          <Typography.Text>Package System Amount: {formatMoney(detail.system_generated_amount)}</Typography.Text>
          <Typography.Text>Package Manual Added Amount: {formatMoney(detail.manual_added_amount)}</Typography.Text>
          <Typography.Text>Effective Amount: {formatMoney(detail.effective_amount)}</Typography.Text>
          <Typography.Text>Reward Ratio: {detail.reward_ratio}</Typography.Text>
          <Typography.Text>Estimated Reward: {formatMoney(detail.estimated_reward_amount)}</Typography.Text>
          <Table dataSource={detail.items ?? []} rowKey="id" size="small" pagination={false} columns={itemColumns} />
          <Table dataSource={detail.manual_add_logs ?? []} rowKey="id" size="small" pagination={false} columns={logColumns} />
        </Space>
      ) : null}
    </Modal>
  );
}
