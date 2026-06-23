import { useCallback, useMemo, useState } from "react";
import { Button, message, Select, Table, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";
import type { EmbeddedSignupSession } from "../../services/api";
import { completeEmbeddedSignupSession, failEmbeddedSignupSession } from "../../services/api";
import { stageLabel, sourceLabel, shortTs } from "./utils";
import { SignupProgressPanel } from "./SignupProgressPanel";

interface SignupListTabProps {
  sessions: EmbeddedSignupSession[];
  focusedAccountId: string;
  onRefresh: () => void;
  accountOptions: { value: string; label: string }[];
}

export function SignupListTab({ sessions, focusedAccountId, onRefresh, accountOptions }: SignupListTabProps) {
  const [filterStatus, setFilterStatus] = useState<string>("");
  const [expandedSessionId, setExpandedSessionId] = useState<string | null>(null);

  const filtered = useMemo(() => {
    let result = sessions;
    if (focusedAccountId) result = result.filter((s) => s.account_id === focusedAccountId);
    if (filterStatus) result = result.filter((s) => s.status === filterStatus);
    return result;
  }, [sessions, focusedAccountId, filterStatus]);

  const handleComplete = useCallback(async (sessionId: string) => {
    try {
      await completeEmbeddedSignupSession(sessionId, {});
      message.success("已完成注册");
      onRefresh();
    } catch { message.error("操作失败"); }
  }, [onRefresh]);

  const handleFail = useCallback(async (sessionId: string) => {
    try {
      await failEmbeddedSignupSession(sessionId, { error_message: "手动标记失败", event_source: "operator" });
      message.success("已标记失败");
      onRefresh();
    } catch { message.error("操作失败"); }
  }, [onRefresh]);

  const columns: ColumnsType<EmbeddedSignupSession> = [
    { title: "会话 ID", dataIndex: "session_id", width: 120, ellipsis: true, render: (v: string) => <span style={{ fontSize: 10, fontFamily: "monospace", color: "#888" }}>{v}</span> },
    { title: "名称", dataIndex: "display_name", width: 100, ellipsis: true },
    {
      title: "状态", dataIndex: "status", width: 70,
      render: (v: string) => <Tag color={v === "created" ? "processing" : v === "completed" ? "success" : "error"} style={{ margin: 0, fontSize: 10 }}>{v}</Tag>,
    },
    { title: "阶段", dataIndex: "completion_stage", width: 90, render: (v: string) => <span style={{ fontSize: 11 }}>{stageLabel(v)}</span> },
    { title: "来源", dataIndex: "event_source", width: 70, render: (v: string) => <span style={{ fontSize: 10, color: "#888" }}>{sourceLabel(v)}</span> },
    { title: "WABA", dataIndex: "linked_waba_id", width: 110, ellipsis: true, render: (v: string | null) => v ? <span style={{ fontSize: 10, fontFamily: "monospace", color: "#aaa" }}>{v}</span> : <span style={{ color: "#ccc" }}>-</span> },
    { title: "最后回调", dataIndex: "callback_received_at", width: 90, render: (v: string | null) => <span style={{ fontSize: 11, color: "#aaa" }}>{shortTs(v)}</span> },
    {
      title: "操作", key: "actions", width: 120,
      render: (_: unknown, r: EmbeddedSignupSession) => (
        <div style={{ display: "flex", gap: 4 }}>
          <Button size="small" style={{ fontSize: 10, padding: "0 4px", height: 22 }}
            onClick={() => setExpandedSessionId(expandedSessionId === r.session_id ? null : r.session_id)}>
            {expandedSessionId === r.session_id ? "收起" : "进度"}
          </Button>
          {r.status === "created" && (
            <>
              <Button size="small" type="primary" style={{ fontSize: 10, padding: "0 4px", height: 22 }}
                onClick={() => handleComplete(r.session_id)}>完成</Button>
              <Button size="small" danger style={{ fontSize: 10, padding: "0 4px", height: 22 }}
                onClick={() => handleFail(r.session_id)}>失败</Button>
            </>
          )}
        </div>
      ),
    },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ padding: "0 0 8px", flexShrink: 0, display: "flex", gap: 8, alignItems: "center" }}>
        <Select size="small" allowClear placeholder="状态" value={filterStatus || undefined} onChange={setFilterStatus} style={{ width: 100 }}
          options={["created", "completed", "failed"].map((v) => ({ label: v, value: v }))} />
        <span style={{ fontSize: 11, color: "#999" }}>共 {filtered.length} 个会话</span>
      </div>
      <div style={{ flex: 1, minHeight: 0, overflow: "auto" }}>
        <Table<EmbeddedSignupSession>
          size="small"
          rowKey="session_id"
          columns={columns}
          dataSource={filtered}
          pagination={false}
          scroll={{ y: "100%" }}
          expandable={{
            expandedRowRender: (r) => expandedSessionId === r.session_id ? (
              <SignupProgressPanel session={r} onRefresh={onRefresh} />
            ) : null,
            expandedRowKeys: expandedSessionId ? [expandedSessionId] : [],
            showExpandColumn: false,
          }}
        />
      </div>
    </div>
  );
}
