import { Button, Empty, Input, InputNumber, Select, Space, Table, Typography } from "antd";

import type { TaskSystemConfig, TaskSystemConfigAuditLog } from "../../services/api";

type Option = {
  label: string;
  value: string;
};

type TaskSystemConfigPanelProps = {
  accountOptions: Option[];
  settingsAccountId: string | undefined;
  settingsSiteId: string | undefined;
  settingsSiteOptions: Option[];
  taskSystemConfig: TaskSystemConfig | null;
  taskSystemConfigAuditLogs: TaskSystemConfigAuditLog[];
  issuePlanOptions: Option[];
  error: string | null;
  saving: boolean;
  onAccountChange: (value: string | undefined) => void;
  onSiteChange: (value: string | undefined) => void;
  onSave: () => void;
  onUpdateConfig: (patch: Partial<TaskSystemConfig>) => void;
  formatDate: (value: string | null | undefined) => string;
};

export function TaskSystemConfigPanel({
  accountOptions,
  settingsAccountId,
  settingsSiteId,
  settingsSiteOptions,
  taskSystemConfig,
  taskSystemConfigAuditLogs,
  issuePlanOptions,
  error,
  saving,
  onAccountChange,
  onSiteChange,
  onSave,
  onUpdateConfig,
  formatDate,
}: TaskSystemConfigPanelProps) {
  return (
    <div>
      <Space wrap style={{ marginBottom: 12 }}>
        <Select
          placeholder="选择账号"
          allowClear
          data-testid="task-settings-account-select"
          style={{ width: 180 }}
          value={settingsAccountId}
          onChange={onAccountChange}
          options={accountOptions}
        />
        <Select
          placeholder="选择站点"
          allowClear
          data-testid="task-settings-site-select"
          style={{ width: 180 }}
          value={settingsSiteId}
          onChange={onSiteChange}
          options={settingsSiteOptions}
        />
        <Button size="small" type="primary" onClick={onSave} loading={saving}>
          保存设置
        </Button>
      </Space>
      {error ? (
        <Typography.Text type="danger" style={{ display: "block", marginBottom: 8 }}>
          {error}
        </Typography.Text>
      ) : null}
      {taskSystemConfig ? (
        <Space direction="vertical" style={{ width: "100%" }} size={12}>
          <Typography.Text strong>系统设置</Typography.Text>
          <Space wrap style={{ width: "100%" }}>
            <Input
              value={taskSystemConfig.whatsappBindingRewardAmount}
              onChange={(event) => onUpdateConfig({ whatsappBindingRewardAmount: event.target.value })}
              addonBefore="绑定奖励"
              style={{ width: 220 }}
            />
            <Input
              value={taskSystemConfig.certifiedRechargeThreshold}
              onChange={(event) => onUpdateConfig({ certifiedRechargeThreshold: event.target.value })}
              addonBefore="认证门槛"
              style={{ width: 220 }}
            />
            <Input
              value={taskSystemConfig.minTaskBalanceTransferPromptAmount}
              onChange={(event) => onUpdateConfig({ minTaskBalanceTransferPromptAmount: event.target.value })}
              addonBefore="转余额提示"
              style={{ width: 240 }}
            />
            <InputNumber
              value={taskSystemConfig.maxActiveBatchesPerUser}
              onChange={(value) => onUpdateConfig({ maxActiveBatchesPerUser: Number(value ?? 1) })}
              min={1}
              style={{ width: 180 }}
            />
            <InputNumber
              value={taskSystemConfig.maxActivePackagesPerUser}
              onChange={(value) => onUpdateConfig({ maxActivePackagesPerUser: Number(value ?? 1) })}
              min={1}
              style={{ width: 200 }}
            />
            <Select
              value={taskSystemConfig.newbiePlanId ?? undefined}
              onChange={(value) => onUpdateConfig({ newbiePlanId: value ?? null })}
              allowClear
              style={{ width: 220 }}
              options={issuePlanOptions}
              placeholder="新手计划"
            />
            <Select
              value={taskSystemConfig.officialPlanId ?? undefined}
              onChange={(value) => onUpdateConfig({ officialPlanId: value ?? null })}
              allowClear
              style={{ width: 220 }}
              options={issuePlanOptions}
              placeholder="正式计划"
            />
          </Space>
          <Typography.Text strong>Recent Audit Logs</Typography.Text>
          <Table
            dataSource={taskSystemConfigAuditLogs}
            columns={[
              { title: "Action", dataIndex: "action", key: "action", width: 220 },
              { title: "Actor", dataIndex: "actor_id", key: "actor_id", width: 180 },
              { title: "Target", dataIndex: "target_id", key: "target_id", width: 180 },
              {
                title: "Time",
                dataIndex: "created_at",
                key: "created_at",
                width: 180,
                render: (value: string | null | undefined) => formatDate(value),
              },
            ]}
            rowKey="id"
            size="small"
            pagination={false}
          />
        </Space>
      ) : (
        <Empty description="请先选择账号并加载任务系统配置。" />
      )}
    </div>
  );
}
