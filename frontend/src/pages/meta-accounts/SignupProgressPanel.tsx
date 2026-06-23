import { useCallback } from "react";
import { Button, Descriptions, message, Steps, Tag } from "antd";
import type { EmbeddedSignupSession } from "../../services/api";
import { completeEmbeddedSignupSession, failEmbeddedSignupSession } from "../../services/api";
import { stageLabel, shortTs } from "./utils";

interface SignupProgressPanelProps {
  session: EmbeddedSignupSession;
  onRefresh: () => void;
}

const STAGES = [
  "pending_callback",
  "callback_recorded",
  "remote_confirmed",
  "local_waba_linked",
  "webhook_verification_pending",
];

export function SignupProgressPanel({ session, onRefresh }: SignupProgressPanelProps) {
  const currentIdx = STAGES.indexOf(session.completion_stage ?? "");
  const isFailed = session.completion_stage === "failed" || session.status === "failed";

  const handleComplete = useCallback(async () => {
    try {
      await completeEmbeddedSignupSession(session.session_id, {});
      message.success("已完成注册");
      onRefresh();
    } catch { message.error("操作失败"); }
  }, [session.session_id, onRefresh]);

  const handleFail = useCallback(async () => {
    try {
      await failEmbeddedSignupSession(session.session_id, {
        error_message: "手动标记失败",
        event_source: "operator",
      });
      message.success("已标记失败");
      onRefresh();
    } catch { message.error("操作失败"); }
  }, [session.session_id, onRefresh]);

  return (
    <div style={{ padding: "8px 0" }}>
      <Steps
        size="small"
        current={isFailed ? -1 : currentIdx >= 0 ? currentIdx : 0}
        status={isFailed ? "error" : currentIdx >= 0 ? "process" : "wait"}
        items={STAGES.map((s) => {
          const idx = STAGES.indexOf(s);
          let status: "wait" | "process" | "finish" | "error" = "wait";
          if (isFailed) status = "error";
          else if (idx < currentIdx) status = "finish";
          else if (idx === currentIdx) status = "process";
          return { title: stageLabel(s), status };
        })}
        style={{ marginBottom: 12 }}
      />
      <Descriptions size="small" column={2} colon={false}>
        <Descriptions.Item label="WABA ID">
          {session.linked_waba_id ? (
            <span style={{ fontSize: 11, fontFamily: "monospace" }}>{session.linked_waba_id}</span>
          ) : <span style={{ color: "#ccc" }}>-</span>}
        </Descriptions.Item>
        <Descriptions.Item label="Portfolio ID">
          {session.meta_business_portfolio_id ? (
            <span style={{ fontSize: 11, fontFamily: "monospace" }}>{session.meta_business_portfolio_id}</span>
          ) : <span style={{ color: "#ccc" }}>-</span>}
        </Descriptions.Item>
        <Descriptions.Item label="号码数">{session.linked_phone_number_ids.length}</Descriptions.Item>
        <Descriptions.Item label="">
          {session.authorization_code_present && <Tag color="blue" style={{ fontSize: 10 }}>Auth Code</Tag>}
          {session.system_user_access_token_present && <Tag color="green" style={{ fontSize: 10 }}>Token</Tag>}
          {session.remote_confirmed && <Tag color="cyan" style={{ fontSize: 10 }}>远程确认</Tag>}
        </Descriptions.Item>
        <Descriptions.Item label="完成时间">{shortTs(session.completed_at)}</Descriptions.Item>
        <Descriptions.Item label="错误信息">
          {session.error_message ? (
            <span style={{ color: "#ff4d4f", fontSize: 11 }}>{session.error_message}</span>
          ) : <span style={{ color: "#ccc" }}>-</span>}
        </Descriptions.Item>
      </Descriptions>
      {session.status === "created" && (
        <div style={{ marginTop: 8, display: "flex", gap: 8 }}>
          <Button size="small" type="primary" onClick={handleComplete}>手动完成</Button>
          <Button size="small" danger onClick={handleFail}>标记失败</Button>
        </div>
      )}
    </div>
  );
}
