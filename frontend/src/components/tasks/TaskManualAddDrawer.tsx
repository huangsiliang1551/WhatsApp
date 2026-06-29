import type { ReactElement } from "react";
import { Button, Input, Modal, Space, Table, Typography } from "antd";
import type { TableProps } from "antd";

import type { TaskManualAddCandidate, TaskManualAddPreviewResponse } from "../../services/api";

type TaskManualAddDrawerProps = {
  open: boolean;
  loading?: boolean;
  submitting?: boolean;
  previewLoading?: boolean;
  candidates: TaskManualAddCandidate[];
  selectedIds: string[];
  reason: string;
  notifyUser?: boolean;
  userNoticeText?: string;
  preview: TaskManualAddPreviewResponse | null;
  onClose: () => void;
  onSubmit: () => void;
  onReasonChange: (value: string) => void;
  onNotifyUserChange?: (value: boolean) => void;
  onUserNoticeTextChange?: (value: string) => void;
  onToggleCandidate: (candidateId: string, checked: boolean) => void;
  onPreview: () => void;
  formatMoney: (value: number | string | null | undefined) => string;
  columns: TableProps<TaskManualAddCandidate>["columns"];
};

export function TaskManualAddDrawer({
  open,
  loading = false,
  submitting = false,
  previewLoading = false,
  candidates,
  selectedIds,
  reason,
  preview,
  onClose,
  onSubmit,
  onReasonChange,
  onToggleCandidate,
  onPreview,
  formatMoney,
  columns,
}: TaskManualAddDrawerProps): ReactElement {
  return (
    <Modal
      title="Manual Add"
      open={open}
      onCancel={onClose}
      onOk={onSubmit}
      confirmLoading={submitting}
      okText="Submit Manual Add"
      cancelText="Close"
    >
      <Space direction="vertical" style={{ width: "100%" }} size={12}>
        {loading ? <Typography.Text>Loading candidates...</Typography.Text> : null}
        <Typography.Text strong>Preview Manual Add Impact</Typography.Text>
        <Input.TextArea rows={2} value={reason} onChange={(event) => onReasonChange(event.target.value)} placeholder="Manual add reason" />
        <Space direction="vertical" style={{ width: "100%" }} size={4}>
          {candidates.map((item) => {
            const checked = selectedIds.includes(item.id);
            return (
              <label key={item.id}>
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={(event) => onToggleCandidate(item.id, event.currentTarget.checked)}
                />
                {` ${item.product_name} (${formatMoney(item.price)})`}
              </label>
            );
          })}
        </Space>
        <Button onClick={onPreview} loading={previewLoading}>Preview Manual Add Impact</Button>
        {preview ? (
          <Space direction="vertical" style={{ width: "100%" }} size={4}>
            <Typography.Text>Candidates: {preview.candidate_count}</Typography.Text>
            <Typography.Text>Added Items: {preview.added_item_count}</Typography.Text>
            <Typography.Text>Added Amount: {formatMoney(preview.added_amount)}</Typography.Text>
            <Typography.Text>Package Planned Amount: {formatMoney(preview.package_planned_amount)}</Typography.Text>
            <Typography.Text>Package System Amount: {formatMoney(preview.package_system_generated_amount)}</Typography.Text>
            <Typography.Text>
              Package Manual Added Amount: {formatMoney(preview.package_manual_added_amount_before)} {"->"} {formatMoney(preview.package_manual_added_amount_after)}
            </Typography.Text>
            <Typography.Text>
              Effective Amount: {formatMoney(preview.package_effective_amount_before)} {"->"} {formatMoney(preview.package_effective_amount_after)}
            </Typography.Text>
            <Typography.Text>Reward Ratio: {preview.reward_ratio}</Typography.Text>
            <Typography.Text>
              Estimated Reward: {formatMoney(preview.estimated_reward_amount_before)} {"->"} {formatMoney(preview.estimated_reward_amount_after)}
            </Typography.Text>
          </Space>
        ) : null}
        <Table dataSource={candidates} rowKey="id" size="small" pagination={false} columns={columns} />
      </Space>
    </Modal>
  );
}
