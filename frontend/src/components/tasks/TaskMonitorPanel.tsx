import type { ReactElement } from "react";
import { Button, Input, Select, Space, Table, Typography } from "antd";
import type { TableProps } from "antd";

import type {
  TaskAlertRule,
  TaskGenerationRun,
  TaskMonitorAlertEvent,
  TaskMonitorQueryParams,
  TaskMonitorRow,
  TaskMonitorSavedView,
} from "../../services/api";
import { TaskAlertRuleEditor } from "./TaskAlertRuleEditor";

type AccountOption = { label: string; value: string };

type TaskMonitorPanelProps = {
  accountOptions: AccountOption[];
  filterAccount?: string;
  onFilterAccountChange: (value: string | undefined) => void;
  monitorFilters: TaskMonitorQueryParams;
  onMonitorFilterChange: (patch: Partial<TaskMonitorQueryParams>) => void;
  onApplyFilters: () => void;
  onResetFilters: () => void;
  onCreateSavedView: () => void;
  onCreateAlertRule: () => void;
  monitorError?: string | null;
  monitorConfigError?: string | null;
  generationRuns: TaskGenerationRun[];
  generationRunColumns: TableProps<TaskGenerationRun>["columns"];
  savedViews: TaskMonitorSavedView[];
  savedViewColumns: TableProps<TaskMonitorSavedView>["columns"];
  alertRules: TaskAlertRule[];
  alertRuleColumns: TableProps<TaskAlertRule>["columns"];
  alertEvents: TaskMonitorAlertEvent[];
  alertEventColumns: TableProps<TaskMonitorAlertEvent>["columns"];
  monitorRows: TaskMonitorRow[];
  monitorRowColumns: TableProps<TaskMonitorRow>["columns"];
  loading?: boolean;
  configLoading?: boolean;
};

export function TaskMonitorPanel({
  accountOptions,
  filterAccount,
  onFilterAccountChange,
  monitorFilters,
  onMonitorFilterChange,
  onApplyFilters,
  onResetFilters,
  onCreateSavedView,
  onCreateAlertRule,
  monitorError,
  monitorConfigError,
  generationRuns,
  generationRunColumns,
  savedViews,
  savedViewColumns,
  alertRules,
  alertRuleColumns,
  alertEvents,
  alertEventColumns,
  monitorRows,
  monitorRowColumns,
  loading = false,
  configLoading = false,
}: TaskMonitorPanelProps): ReactElement {
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
        <Input
          allowClear
          placeholder="Search User / Public ID"
          style={{ width: 180 }}
          value={monitorFilters.user_query ?? ""}
          onChange={(event) => onMonitorFilterChange({ user_query: event.target.value || undefined })}
        />
        <Select
          allowClear
          placeholder="Filter Status"
          style={{ width: 140 }}
          value={monitorFilters.status}
          onChange={(value) => onMonitorFilterChange({ status: value })}
          options={[
            { label: "Active", value: "active" },
            { label: "Completed", value: "completed" },
            { label: "Paused", value: "paused" },
            { label: "Expired", value: "expired" },
            { label: "Cancelled", value: "cancelled" },
          ]}
        />
        <Select
          allowClear
          placeholder="Has Manual Add"
          style={{ width: 140 }}
          value={monitorFilters.has_manual_add}
          onChange={(value) => onMonitorFilterChange({ has_manual_add: value })}
          options={[
            { label: "Yes", value: true },
            { label: "No", value: false },
          ]}
        />
        <Input
          allowClear
          placeholder="Latest Manual Add Operator"
          style={{ width: 190 }}
          value={monitorFilters.latest_manual_add_operator_id ?? ""}
          onChange={(event) => onMonitorFilterChange({ latest_manual_add_operator_id: event.target.value || undefined })}
        />
        <Input
          placeholder="Day Planned Min"
          style={{ width: 150 }}
          value={monitorFilters.day_planned_amount_min ?? ""}
          onChange={(event) => onMonitorFilterChange({ day_planned_amount_min: event.target.value || undefined })}
        />
        <Input
          placeholder="Day Planned Max"
          style={{ width: 150 }}
          value={monitorFilters.day_planned_amount_max ?? ""}
          onChange={(event) => onMonitorFilterChange({ day_planned_amount_max: event.target.value || undefined })}
        />
        <Input
          placeholder="Day Manual Added Min"
          style={{ width: 170 }}
          value={monitorFilters.day_manual_added_amount_min ?? ""}
          onChange={(event) => onMonitorFilterChange({ day_manual_added_amount_min: event.target.value || undefined })}
        />
        <Input
          placeholder="Day Manual Added Max"
          style={{ width: 170 }}
          value={monitorFilters.day_manual_added_amount_max ?? ""}
          onChange={(event) => onMonitorFilterChange({ day_manual_added_amount_max: event.target.value || undefined })}
        />
        <Input
          placeholder="Day Effective Min"
          style={{ width: 150 }}
          value={monitorFilters.day_effective_amount_min ?? ""}
          onChange={(event) => onMonitorFilterChange({ day_effective_amount_min: event.target.value || undefined })}
        />
        <Input
          placeholder="Day Effective Max"
          style={{ width: 150 }}
          value={monitorFilters.day_effective_amount_max ?? ""}
          onChange={(event) => onMonitorFilterChange({ day_effective_amount_max: event.target.value || undefined })}
        />
        <Input
          placeholder="Planned Amount Min"
          style={{ width: 160 }}
          value={monitorFilters.planned_amount_min ?? ""}
          onChange={(event) => onMonitorFilterChange({ planned_amount_min: event.target.value || undefined })}
        />
        <Input
          placeholder="Planned Amount Max"
          style={{ width: 160 }}
          value={monitorFilters.planned_amount_max ?? ""}
          onChange={(event) => onMonitorFilterChange({ planned_amount_max: event.target.value || undefined })}
        />
        <Input
          placeholder="Manual Added Min"
          style={{ width: 160 }}
          value={monitorFilters.manual_added_amount_min ?? ""}
          onChange={(event) => onMonitorFilterChange({ manual_added_amount_min: event.target.value || undefined })}
        />
        <Input
          placeholder="Manual Added Max"
          style={{ width: 160 }}
          value={monitorFilters.manual_added_amount_max ?? ""}
          onChange={(event) => onMonitorFilterChange({ manual_added_amount_max: event.target.value || undefined })}
        />
        <Input
          placeholder="Effective Amount Min"
          style={{ width: 160 }}
          value={monitorFilters.effective_amount_min ?? ""}
          onChange={(event) => onMonitorFilterChange({ effective_amount_min: event.target.value || undefined })}
        />
        <Input
          placeholder="Effective Amount Max"
          style={{ width: 160 }}
          value={monitorFilters.effective_amount_max ?? ""}
          onChange={(event) => onMonitorFilterChange({ effective_amount_max: event.target.value || undefined })}
        />
        <Input
          placeholder="Current Product Min"
          style={{ width: 160 }}
          value={monitorFilters.current_product_amount_min ?? ""}
          onChange={(event) => onMonitorFilterChange({ current_product_amount_min: event.target.value || undefined })}
        />
        <Input
          placeholder="Current Product Max"
          style={{ width: 160 }}
          value={monitorFilters.current_product_amount_max ?? ""}
          onChange={(event) => onMonitorFilterChange({ current_product_amount_max: event.target.value || undefined })}
        />
        <Input
          placeholder="Recharge Min"
          style={{ width: 140 }}
          value={monitorFilters.total_recharge_amount_min ?? ""}
          onChange={(event) => onMonitorFilterChange({ total_recharge_amount_min: event.target.value || undefined })}
        />
        <Input
          placeholder="Recharge Max"
          style={{ width: 140 }}
          value={monitorFilters.total_recharge_amount_max ?? ""}
          onChange={(event) => onMonitorFilterChange({ total_recharge_amount_max: event.target.value || undefined })}
        />
        <Input
          placeholder="Withdraw Min"
          style={{ width: 140 }}
          value={monitorFilters.total_withdraw_amount_min ?? ""}
          onChange={(event) => onMonitorFilterChange({ total_withdraw_amount_min: event.target.value || undefined })}
        />
        <Input
          placeholder="Withdraw Max"
          style={{ width: 140 }}
          value={monitorFilters.total_withdraw_amount_max ?? ""}
          onChange={(event) => onMonitorFilterChange({ total_withdraw_amount_max: event.target.value || undefined })}
        />
        <Button size="small" type="primary" onClick={onApplyFilters}>Apply Filters</Button>
        <Button size="small" onClick={onResetFilters}>Reset Filters</Button>
        <Button size="small" onClick={onCreateSavedView}>New Saved View</Button>
        <Button size="small" onClick={onCreateAlertRule}>New Alert Rule</Button>
      </Space>
      {monitorError ? <Typography.Text type="danger" style={{ display: "block", marginBottom: 8 }}>{monitorError}</Typography.Text> : null}
      {monitorConfigError ? <Typography.Text type="danger" style={{ display: "block", marginBottom: 8 }}>{monitorConfigError}</Typography.Text> : null}
      <Space direction="vertical" style={{ width: "100%", marginBottom: 12 }} size={8}>
        <Typography.Text strong>Generation Runs</Typography.Text>
        <Table
          dataSource={generationRuns}
          columns={generationRunColumns}
          rowKey="id"
          size="small"
          loading={configLoading}
          pagination={false}
        />
        <TaskAlertRuleEditor
          savedViews={savedViews}
          savedViewColumns={savedViewColumns}
          alertRules={alertRules}
          alertRuleColumns={alertRuleColumns}
          alertEvents={alertEvents}
          alertEventColumns={alertEventColumns}
          loading={configLoading}
        />
      </Space>
      <Table
        dataSource={monitorRows}
        columns={monitorRowColumns}
        rowKey="package_id"
        size="small"
        loading={loading}
        pagination={{ pageSize: 20, showSizeChanger: true }}
        scroll={{ y: "calc(100vh - 440px)" }}
      />
    </div>
  );
}
