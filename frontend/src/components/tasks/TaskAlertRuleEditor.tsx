import type { ReactElement } from "react";
import { Table, Typography } from "antd";
import type { TableProps } from "antd";

import type { TaskAlertRule, TaskMonitorAlertEvent, TaskMonitorSavedView } from "../../services/api";

type TaskAlertRuleEditorProps = {
  savedViews: TaskMonitorSavedView[];
  savedViewColumns: TableProps<TaskMonitorSavedView>["columns"];
  alertRules: TaskAlertRule[];
  alertRuleColumns: TableProps<TaskAlertRule>["columns"];
  alertEvents: TaskMonitorAlertEvent[];
  alertEventColumns: TableProps<TaskMonitorAlertEvent>["columns"];
  loading?: boolean;
};

export function TaskAlertRuleEditor({
  savedViews,
  savedViewColumns,
  alertRules,
  alertRuleColumns,
  alertEvents,
  alertEventColumns,
  loading = false,
}: TaskAlertRuleEditorProps): ReactElement {
  return (
    <>
      <Typography.Text strong>Saved Views</Typography.Text>
      <Table
        dataSource={savedViews}
        columns={savedViewColumns}
        rowKey="id"
        size="small"
        loading={loading}
        pagination={false}
      />
      <Typography.Text strong>Alert Rules</Typography.Text>
      <Table
        dataSource={alertRules}
        columns={alertRuleColumns}
        rowKey="id"
        size="small"
        loading={loading}
        pagination={false}
      />
      <Typography.Text strong>Alert Events</Typography.Text>
      <Table
        dataSource={alertEvents}
        columns={alertEventColumns}
        rowKey="id"
        size="small"
        loading={loading}
        pagination={false}
      />
    </>
  );
}
