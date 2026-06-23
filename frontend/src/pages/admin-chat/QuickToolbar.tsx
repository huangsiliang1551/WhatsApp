import { type JSX, useMemo, useState } from "react";

import { Button, Input, Popover, Select, Space, Tooltip } from "antd";
import { QuestionCircleOutlined } from "@ant-design/icons";

import type { ConversationSummary, MediaAssetView, MessageTemplateView } from "../../services/api";

const { TextArea } = Input;

const SAMPLE_THREADS = [
  { label: "西语示例", text: "hola, mi pedido no ha llegado", lang: "es" },
  { label: "法语示例", text: "bonjour, je veux modifier ma commande", lang: "fr" },
  { label: "中文示例", text: "你好我想查询我的订单", lang: "zh-CN" },
];

export interface QuickToolbarProps {
  conversation: ConversationSummary | null;
  templates: MessageTemplateView[];
  mediaAssets: MediaAssetView[];
  onSendTemplate: (templateId: string, variables: Record<string, string>) => void;
  onSendMedia: (assetId: string, caption?: string, fileName?: string) => void;
  onMockInbound: (text: string, language?: string) => void;
  disabled: boolean;
  /** 快捷回复选择回调 (FX-006) */
  onCannedResponse?: () => void;
}

function getSendableTemplates(t: MessageTemplateView[], conv: ConversationSummary | null): MessageTemplateView[] {
  return !conv ? [] : t.filter(i => i.account_id === conv.account_id && i.status === "APPROVED" && (!i.waba_id || !conv.waba_id || i.waba_id === conv.waba_id));
}

function getSendableMedia(a: MediaAssetView[], conv: ConversationSummary | null): MediaAssetView[] {
  return !conv ? [] : a.filter(i => i.account_id === conv.account_id && i.is_active && (!i.waba_id || !conv.waba_id || i.waba_id === conv.waba_id));
}

export function QuickToolbar({
  conversation,
  templates,
  mediaAssets,
  onSendTemplate,
  onSendMedia,
  onMockInbound,
  disabled,
  onCannedResponse,
}: QuickToolbarProps): JSX.Element {
  const sendableTmpls = useMemo(() => getSendableTemplates(templates, conversation), [templates, conversation]);
  const sendableMedia = useMemo(() => getSendableMedia(mediaAssets, conversation), [mediaAssets, conversation]);

  const [selTmpl, setSelTmpl] = useState("");
  const [tmplVars, setTmplVars] = useState("");
  const [selMed, setSelMed] = useState("");
  const [medCap, setMedCap] = useState("");
  const [medFn, setMedFn] = useState("");
  const [mockText, setMockText] = useState("");
  const [mockLang, setMockLang] = useState("zh-CN");

  const selTemplate = useMemo(() => sendableTmpls.find(t => t.template_id === selTmpl) ?? null, [selTmpl, sendableTmpls]);
  const selMedia = useMemo(() => sendableMedia.find(m => m.asset_id === selMed) ?? null, [selMed, sendableMedia]);

  const parseVariables = (input: string): Record<string, string> => {
    const r: Record<string, string> = {};
    input.split(/\r?\n/).map(l => l.trim()).filter(Boolean).forEach(l => {
      const sep = l.indexOf("=");
      if (sep > 0) {
        r[l.slice(0, sep).trim()] = l.slice(sep + 1).trim();
      }
    });
    return r;
  };

  const templateContent = (
    <div style={{ width: 280 }}>
      <Space direction="vertical" size={8} style={{ width: "100%" }}>
        <Select
          size="small"
          style={{ width: "100%" }}
          placeholder="选择模板"
          options={sendableTmpls.map(t => ({ label: `${t.name} (${t.language})`, value: t.template_id }))}
          value={selTmpl || undefined}
          onChange={(v) => setSelTmpl(v)}
        />
        {selTemplate && (
          <>
            <TextArea
              rows={4}
              size="small"
              placeholder="填入变量值，每行一个 key=value"
              value={tmplVars}
              onChange={(e) => setTmplVars(e.target.value)}
            />
            <div style={{ fontSize: 11, color: "#999", padding: "4px 8px", background: "#fafafa", borderRadius: 4 }}>
              示例: {Object.entries(selTemplate.sample_variables).map(([k, v]) => `${k}=${v}`).join(", ")}
            </div>
            <Button
              size="small"
              type="primary"
              block
              disabled={!selTmpl}
              onClick={() => {
                if (conversation) {
                  onSendTemplate(selTmpl, parseVariables(tmplVars));
                  setSelTmpl("");
                  setTmplVars("");
                }
              }}
            >
              发送模板
            </Button>
          </>
        )}
      </Space>
    </div>
  );

  const mediaContent = (
    <div style={{ width: 280 }}>
      <Space direction="vertical" size={8} style={{ width: "100%" }}>
        <Select
          size="small"
          style={{ width: "100%" }}
          placeholder="选择媒体"
          options={sendableMedia.map(m => ({ label: m.name ?? m.asset_id, value: m.asset_id }))}
          value={selMed || undefined}
          onChange={(v) => setSelMed(v)}
        />
        <Input size="small" placeholder="Caption (可选)" value={medCap} onChange={(e) => setMedCap(e.target.value)} />
        <Input size="small" placeholder="文件名 (可选)" value={medFn} onChange={(e) => setMedFn(e.target.value)} />
        <Button
          size="small"
          type="primary"
          block
          disabled={!selMed}
          onClick={() => {
            if (conversation) {
              onSendMedia(selMed, medCap || undefined, medFn || undefined);
              setSelMed("");
              setMedCap("");
              setMedFn("");
            }
          }}
        >
          发送媒体
        </Button>
      </Space>
    </div>
  );

  const mockContent = (
    <div style={{ width: 300 }}>
      <Space direction="vertical" size={8} style={{ width: "100%" }}>
        <Select
          size="small"
          style={{ width: 120 }}
          options={[
            { label: "中文 (zh-CN)", value: "zh-CN" },
            { label: "西班牙语 (es)", value: "es" },
            { label: "法语 (fr)", value: "fr" },
            { label: "英语 (en)", value: "en" },
          ]}
          value={mockLang}
          onChange={(v) => setMockLang(v)}
        />
        <TextArea
          rows={3}
          size="small"
          placeholder="模拟入站消息..."
          value={mockText}
          onChange={(e) => setMockText(e.target.value)}
        />
        <Space size={4}>
          {SAMPLE_THREADS.map((s) => (
            <Button
              key={s.label}
              size="small"
              onClick={() => {
                setMockText(s.text);
                setMockLang(s.lang);
              }}
            >
              {s.label}
            </Button>
          ))}
        </Space>
        <Button
          size="small"
          type="primary"
          block
          disabled={!mockText.trim()}
          onClick={() => {
            if (conversation && mockText.trim()) {
              onMockInbound(mockText.trim(), mockLang);
              setMockText("");
            }
          }}
        >
          模拟入站
        </Button>
      </Space>
    </div>
  );

  const btnStyle: React.CSSProperties = {
    minWidth: 90,
    overflow: "visible",
  };

  return (
    <div
      style={{
        display: "flex",
        gap: 8,
        padding: "4px 12px",
        borderTop: "1px solid #f0f0f0",
        flexShrink: 0,
      }}
    >
      <Popover content={templateContent} title="发送模板" trigger="click" placement="topLeft">
        <Button size="small" disabled={disabled} style={btnStyle}>
          📋 发送模板
        </Button>
      </Popover>
      <Popover content={mediaContent} title="发送媒体" trigger="click" placement="topLeft">
        <Button size="small" disabled={disabled} style={btnStyle}>
          🖼 发送媒体
        </Button>
      </Popover>
      <Popover content={mockContent} title="模拟入站" trigger="click" placement="topLeft">
        <Button size="small" disabled={disabled} style={btnStyle}>
          😀 模拟入站
        </Button>
      </Popover>
      {onCannedResponse && (
        <>
          <Button size="small" disabled={disabled} style={btnStyle} onClick={onCannedResponse}>
            💬 快捷回复
          </Button>
          <Tooltip
            title={
              <div style={{ fontSize: 11, lineHeight: 1.8 }}>
                <div><b>键盘快捷键</b></div>
                <div>Enter → 发送消息</div>
                <div>Shift+Enter → 换行</div>
                <div>Ctrl+Enter → 换行</div>
                <div>Alt+↑/↓ → 切换会话</div>
                <div>Ctrl+F → 搜索消息</div>
                <div>Ctrl+1~9 → 切换标签页</div>
                <div>Ctrl+W → 关闭标签页</div>
              </div>
            }
            placement="topRight"
          >
            <span style={{ cursor: "help", color: "#999", fontSize: 12 }}>
              <QuestionCircleOutlined /> 快捷键
            </span>
          </Tooltip>
        </>
      )}
    </div>
  );
}
