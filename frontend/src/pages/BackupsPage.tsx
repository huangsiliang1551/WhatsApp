import { useCallback, useEffect, useState, type JSX } from "react";
import { Button, Card, Col, Row, Select, Space, Statistic, Table, Tag, Typography, Modal, message } from "antd";
import { withSorter } from "../utils/withSorter";
import { DatabaseOutlined, DownloadOutlined, PlayCircleOutlined, WarningOutlined } from "@ant-design/icons";
import { usePageData } from "../hooks/usePageData";
import { usePermissions } from "../hooks/usePermissions";
import { PageShell } from "../components/PageShell";
import { DangerButton, showSuccess, showError } from "../components/Feedback";
import { listBackups, createBackup, restoreBackup, deleteBackup, getBackupDownloadUrl, type DbBackup } from "../services/api";

function formatBytes(bytes: number): string {
  if (!bytes) return "-";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const TYPE_LABELS: Record<string, string> = { manual: "手动", auto_daily: "每日自动", auto_weekly: "每周自动" };
const TYPE_COLORS: Record<string, string> = { manual: "blue", auto_daily: "green", auto_weekly: "orange" };
const STATUS_LABELS: Record<string, string> = { running: "进行中", completed: "已完成", failed: "失败" };
const STATUS_COLORS: Record<string, string> = { running: "processing", completed: "success", failed: "error" };

export function BackupsPage(): JSX.Element {
  const { can } = usePermissions();
  const [autoSchedule, setAutoSchedule] = useState<string>("off");
  const [creating, setCreating] = useState(false);
  const [restoring, setRestoring] = useState<string | null>(null);
  const [restoreModalOpen, setRestoreModalOpen] = useState(false);
  const [restoreTarget, setRestoreTarget] = useState<DbBackup | null>(null);

  // Load auto-schedule from localStorage
  useEffect(() => {
    try {
      const saved = localStorage.getItem("backup_auto_schedule");
      if (saved) setAutoSchedule(saved);
    } catch { /* ignore */ }
  }, []);

  const saveSchedule = (val: string) => {
    setAutoSchedule(val);
    localStorage.setItem("backup_auto_schedule", val);
    message.success(`自动备份已设为: ${val === "off" ? "关闭" : val === "daily" ? "每天" : "每周"}`);
  };

  const handleCreateBackup = async () => {
    setCreating(true);
    try {
      await createBackup();
      showSuccess("备份任务已启动");
      void reload();
    } catch (e) {
      showError(e instanceof Error ? e.message : "创建备份失败");
    } finally {
      setCreating(false);
    }
  };

  const handleRestore = async () => {
    if (!restoreTarget) return;
    setRestoring(restoreTarget.id);
    try {
      await restoreBackup(restoreTarget.id);
      showSuccess("备份恢复任务已启动");
      setRestoreModalOpen(false);
    } catch (e) {
      showError(e instanceof Error ? e.message : "恢复失败");
    } finally {
      setRestoring(null);
    }
  };

  const handleDelete = async (backup: DbBackup) => {
    try {
      await deleteBackup(backup.id);
      showSuccess("备份已删除");
      void reload();
    } catch (e) {
      showError(e instanceof Error ? e.message : "删除失败");
    }
  };

  const handleDownload = (backup: DbBackup) => {
    const url = getBackupDownloadUrl(backup.id);
    window.open(url, "_blank");
  };

  const { data, loading, error, reload } = usePageData({
    fetcher: useCallback(async () => {
      const backups = await listBackups();
      const runningCount = backups.filter((b) => b.status === "running").length;
      const completedCount = backups.filter((b) => b.status === "completed").length;
      const failedCount = backups.filter((b) => b.status === "failed").length;
      return { backups, runningCount, completedCount, failedCount, totalCount: backups.length };
    }, [])
  });

  const backups = data?.backups ?? [];
  const totalCount = data?.totalCount ?? 0;
  const runningCount = data?.runningCount ?? 0;
  const completedCount = data?.completedCount ?? 0;
  const failedCount = data?.failedCount ?? 0;

  const actions = (
    <Space>
      {can("backups.create") && (
        <Button type="primary" icon={<PlayCircleOutlined />} onClick={handleCreateBackup} loading={creating}>
          立即备份
        </Button>
      )}
      <Select
        value={autoSchedule}
        onChange={saveSchedule}
        style={{ width: 120 }}
        options={[
          { label: "关闭", value: "off" },
          { label: "每天", value: "daily" },
          { label: "每周", value: "weekly" },
        ]}
      />
      <Button size="small" onClick={() => void reload()} loading={loading}>刷新</Button>
    </Space>
  );

  const columns = [
    { title: "文件名", dataIndex: "filename", key: "filename", ellipsis: true },
    { title: "大小", dataIndex: "file_size", key: "file_size", width: 100, render: (v: number) => formatBytes(v) },
    { title: "类型", dataIndex: "backup_type", key: "backup_type", width: 100, render: (v: string) => <Tag color={TYPE_COLORS[v]}>{TYPE_LABELS[v] ?? v}</Tag> },
    { title: "状态", dataIndex: "status", key: "status", width: 100, render: (v: string) => <Tag color={STATUS_COLORS[v]}>{STATUS_LABELS[v] ?? v}</Tag> },
    { title: "完成时间", dataIndex: "completed_at", key: "completed_at", width: 160, render: (v: string) => v ? new Date(v).toLocaleString("zh-CN") : "-" },
    { title: "创建人", dataIndex: "created_by", key: "created_by", width: 120 },
    {
      title: "操作", key: "actions", width: 200,
      render: (_: unknown, r: DbBackup) => (
        <Space size="small">
          {can("backups.restore") && r.status === "completed" && (
            <Button size="small" onClick={() => { setRestoreTarget(r); setRestoreModalOpen(true); }}>
              恢复
            </Button>
          )}
          {r.status === "completed" && (
            <Button size="small" icon={<DownloadOutlined />} onClick={() => handleDownload(r)}>
              下载
            </Button>
          )}
          <DangerButton
            label="删除"
            confirmTitle="确认删除此备份?"
            confirmDescription="此操作不可恢复"
            onConfirm={() => handleDelete(r)}
            type="link"
            danger
          />
        </Space>
      ),
    },
  ];

  return (
    <PageShell title="数据库备份" subtitle="管理和恢复数据库备份" actions={actions}>
      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        <Col span={6}><Card size="small"><Statistic title="总备份数" value={totalCount} prefix={<DatabaseOutlined />} /></Card></Col>
        <Col span={6}><Card size="small"><Statistic title="进行中" value={runningCount} valueStyle={{ color: "#1677ff" }} /></Card></Col>
        <Col span={6}><Card size="small"><Statistic title="已完成" value={completedCount} valueStyle={{ color: "#52c41a" }} /></Card></Col>
        <Col span={6}><Card size="small"><Statistic title="失败" value={failedCount} valueStyle={{ color: failedCount > 0 ? "#ff4d4f" : undefined }} prefix={failedCount > 0 ? <WarningOutlined /> : undefined} /></Card></Col>
      </Row>
      {error && <Typography.Text type="danger" style={{ display: "block", marginBottom: 12 }}>{error}</Typography.Text>}
      <Table dataSource={backups} columns={withSorter(columns)} rowKey="id" size="small" loading={loading}
        pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (t) => `共 ${t} 条` }}
        scroll={{ y: "calc(100vh - 420px)" }}
      />

      <Modal
        title="确认恢复备份"
        open={restoreModalOpen}
        onCancel={() => { setRestoreModalOpen(false); setRestoreTarget(null); }}
        onOk={handleRestore}
        confirmLoading={restoring === restoreTarget?.id}
        okText="确认恢复"
        cancelText="取消"
        okButtonProps={{ danger: true }}
      >
        <Typography.Paragraph>
          确定要恢复备份 <Typography.Text strong>{restoreTarget?.filename}</Typography.Text> 吗？
        </Typography.Paragraph>
        <Typography.Text type="danger">⚠ 恢复操作将覆盖当前数据库，请谨慎操作！</Typography.Text>
      </Modal>
    </PageShell>
  );
}

export default BackupsPage;
