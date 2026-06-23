import { useCallback, useMemo, useState } from "react";
import { message, Select, Switch, Table, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";
import type { MetaPhoneNumberScopeView } from "../../services/api";
import { updateMetaPhoneNumberStatus } from "../../services/api";
import { qualityColor } from "./utils";

interface PhoneListTabProps {
  phones: MetaPhoneNumberScopeView[];
  focusedAccountId: string;
  onRefresh: () => void;
}

export function PhoneListTab({ phones, focusedAccountId, onRefresh }: PhoneListTabProps) {
  const [filterQuality, setFilterQuality] = useState<string>("");
  const [filterRegistered, setFilterRegistered] = useState<string>("");

  const filtered = useMemo(() => {
    let result = phones;
    if (focusedAccountId) result = result.filter((p) => p.account_id === focusedAccountId);
    if (filterQuality) result = result.filter((p) => p.quality_rating === filterQuality);
    if (filterRegistered === "yes") result = result.filter((p) => p.is_registered);
    if (filterRegistered === "no") result = result.filter((p) => !p.is_registered);
    return result;
  }, [phones, focusedAccountId, filterQuality, filterRegistered]);

  const handleToggle = useCallback(
    async (checked: boolean, record: MetaPhoneNumberScopeView) => {
      try {
        await updateMetaPhoneNumberStatus(record.account_id, record.waba_id, record.phone_number_id, {
          is_active: checked,
        });
        message.success(checked ? "已启用" : "已禁用");
        onRefresh();
      } catch {
        message.error("操作失败");
      }
    },
    [onRefresh],
  );

  const columns: ColumnsType<MetaPhoneNumberScopeView> = [
    { title: "账户", dataIndex: "account_display_name", width: 100, ellipsis: true },
    {
      title: "WABA", dataIndex: "waba_id", width: 110, ellipsis: true,
      render: (v: string) => <span style={{ fontSize: 11, fontFamily: "monospace", color: "#888" }}>{v}</span>,
    },
    { title: "号码", dataIndex: "display_phone_number", width: 130 },
    {
      title: "Phone ID", dataIndex: "phone_number_id", width: 120, ellipsis: true,
      render: (v: string) => <span style={{ fontSize: 10, fontFamily: "monospace", color: "#aaa" }}>{v}</span>,
    },
    {
      title: "质量", dataIndex: "quality_rating", width: 70,
      render: (v: string) => <Tag color={qualityColor(v)} style={{ fontSize: 10, margin: 0 }}>{v}</Tag>,
    },
    {
      title: "已注册", dataIndex: "is_registered", width: 70,
      render: (v: boolean) => <Tag color={v ? "success" : "default"} style={{ fontSize: 10, margin: 0 }}>{v ? "是" : "否"}</Tag>,
    },
    {
      title: "启用", dataIndex: "is_active", width: 60,
      render: (v: boolean, r: MetaPhoneNumberScopeView) => (
        <Switch size="small" checked={v} onChange={(checked) => handleToggle(checked, r)} />
      ),
    },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ padding: "0 0 8px", flexShrink: 0, display: "flex", gap: 8, alignItems: "center" }}>
        <Select size="small" allowClear placeholder="质量" value={filterQuality || undefined} onChange={setFilterQuality} style={{ width: 100 }}
          options={["GREEN", "YELLOW", "RED", "UNKNOWN"].map((v) => ({ label: v, value: v }))} />
        <Select size="small" allowClear placeholder="注册状态" value={filterRegistered || undefined} onChange={setFilterRegistered} style={{ width: 100 }}
          options={[{ label: "已注册", value: "yes" }, { label: "未注册", value: "no" }]} />
        <span style={{ fontSize: 11, color: "#999" }}>共 {filtered.length} 条</span>
      </div>
      <div style={{ flex: 1, minHeight: 0, overflow: "auto" }}>
        <Table<MetaPhoneNumberScopeView>
          size="small" rowKey="phone_number_id" columns={columns} dataSource={filtered}
          pagination={false} scroll={{ y: "100%" }}
        />
      </div>
    </div>
  );
}
