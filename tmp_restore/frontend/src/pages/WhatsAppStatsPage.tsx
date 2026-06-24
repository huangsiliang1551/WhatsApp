import { useEffect, useMemo, useRef, useState, type JSX } from "react";

import { Panel } from "../components/Panel";
import {
  getWhatsAppStatsDetail,
  listMetaAccounts,
  rebuildWhatsAppStats,
  type MetaWabaAccount,
  type WhatsAppStatsDailyRow,
  type WhatsAppStatsQueryParams,
  type WhatsAppStatsSummary,
} from "../services/api";
import { useAppStore } from "../stores/appStore";

type FilterDraft = {
  account_id: string;
  waba_id: string;
  phone_number_id: string;
  conversation_origin_type: string;
  conversation_category: string;
  pricing_model: string;
  billable: "all" | "true" | "false";
  hour_bucket: string;
  date_from: string;
  date_to: string;
};

type BreakdownRow = {
  key: string;
  row_count: number;
  inbound_message_count: number;
  outbound_message_count: number;
  delivered_count: number;
  read_count: number;
  failed_count: number;
  billable_count: number;
  estimated_cost: number;
};

type StatCardProps = {
  title: string;
  value: number | string;
  description: string;
};

const DEFAULT_FILTERS: FilterDraft = {
  account_id: "",
  waba_id: "",
  phone_number_id: "",
  conversation_origin_type: "",
  conversation_category: "",
  pricing_model: "",
  billable: "all",
  hour_bucket: "",
  date_from: "",
  date_to: "",
};

const EMPTY_SUMMARY: WhatsAppStatsSummary = {
  conversation_count: 0,
  unique_customer_count: 0,
  inbound_message_count: 0,
  outbound_message_count: 0,
  delivered_count: 0,
  read_count: 0,
  failed_count: 0,
  billable_count: 0,
  estimated_cost: 0,
  estimated_cost_status: "not_applicable",
  estimated_cost_note: null,
};

function StatCard({ title, value, description }: StatCardProps): JSX.Element {
  return (
    <article className="queue-stat-card">
      <strong>{title}</strong>
      <span>{value}</span>
      <p className="muted">{description}</p>
    </article>
  );
}

function formatTimestamp(value: string | null): string {
  if (!value) {
    return "暂无";
  }
  return new Date(value).toLocaleString("zh-CN");
}

function formatCost(value: number): string {
  return value.toFixed(4);
}

function formatHourBucket(value: number | null): string {
  if (value === null) {
    return "全天";
  }
  return `${String(value).padStart(2, "0")}:00`;
}

function formatDimensionValue(value: string | null | undefined, fallback: string): string {
  const normalized = value?.trim();
  return normalized ? normalized : fallback;
}

function formatBillable(value: boolean): string {
  return value ? "可计费" : "不可计费";
}

function toFilterDraft(params: {
  account_id?: string;
  waba_id?: string;
  phone_number_id?: string;
  conversation_origin_type?: string;
  conversation_category?: string;
  pricing_model?: string;
  billable?: boolean;
  hour_bucket?: number;
  date_from?: string;
  date_to?: string;
}): FilterDraft {
  return {
    account_id: params.account_id ?? "",
    waba_id: params.waba_id ?? "",
    phone_number_id: params.phone_number_id ?? "",
    conversation_origin_type: params.conversation_origin_type ?? "",
    conversation_category: params.conversation_category ?? "",
    pricing_model: params.pricing_model ?? "",
    billable:
      params.billable === true ? "true" : params.billable === false ? "false" : DEFAULT_FILTERS.billable,
    hour_bucket:
      typeof params.hour_bucket === "number" && Number.isFinite(params.hour_bucket)
        ? String(params.hour_bucket)
        : "",
    date_from: params.date_from ?? "",
    date_to: params.date_to ?? "",
  };
}

function toQueryParams(filters: FilterDraft): WhatsAppStatsQueryParams {
  return {
    ...(filters.account_id ? { account_id: filters.account_id } : {}),
    ...(filters.waba_id ? { waba_id: filters.waba_id } : {}),
    ...(filters.phone_number_id ? { phone_number_id: filters.phone_number_id } : {}),
    ...(filters.conversation_origin_type
      ? { conversation_origin_type: filters.conversation_origin_type }
      : {}),
    ...(filters.conversation_category
      ? { conversation_category: filters.conversation_category }
      : {}),
    ...(filters.pricing_model ? { pricing_model: filters.pricing_model } : {}),
    ...(filters.billable === "true"
      ? { billable: true }
      : filters.billable === "false"
        ? { billable: false }
        : {}),
    ...(filters.hour_bucket ? { hour_bucket: Number(filters.hour_bucket) } : {}),
    ...(filters.date_from ? { date_from: filters.date_from } : {}),
    ...(filters.date_to ? { date_to: filters.date_to } : {}),
  };
}

function groupRows(
  rows: WhatsAppStatsDailyRow[],
  selector: (row: WhatsAppStatsDailyRow) => string | null | undefined
): BreakdownRow[] {
  const grouped = new Map<string, BreakdownRow>();
  for (const row of rows) {
    const key = selector(row) ?? "未绑定";
    const current =
      grouped.get(key) ??
      ({
        key,
        row_count: 0,
        inbound_message_count: 0,
        outbound_message_count: 0,
        delivered_count: 0,
        read_count: 0,
        failed_count: 0,
        billable_count: 0,
        estimated_cost: 0,
      } satisfies BreakdownRow);
    current.row_count += 1;
    current.inbound_message_count += row.inbound_message_count;
    current.outbound_message_count += row.outbound_message_count;
    current.delivered_count += row.delivered_count;
    current.read_count += row.read_count;
    current.failed_count += row.failed_count;
    current.billable_count += row.billable_count;
    current.estimated_cost += row.estimated_cost;
    grouped.set(key, current);
  }
  return Array.from(grouped.values()).sort(
    (left, right) =>
      right.outbound_message_count - left.outbound_message_count ||
      right.inbound_message_count - left.inbound_message_count ||
      left.key.localeCompare(right.key)
  );
}

function getAccountLabel(accountId: string, accountMap: Map<string, MetaWabaAccount>): string {
  const matched = accountMap.get(accountId);
  return matched ? `${matched.display_name} (${accountId})` : accountId;
}

function normalizeScopedFilters(
  nextFilters: FilterDraft,
  metaAccounts: MetaWabaAccount[]
): FilterDraft {
  const scopedAccounts = metaAccounts.filter((account) =>
    nextFilters.account_id ? account.account_id === nextFilters.account_id : true
  );
  const allowedWabaIds = new Set(scopedAccounts.map((account) => account.waba_id));
  const resolvedWabaId =
    nextFilters.waba_id && allowedWabaIds.has(nextFilters.waba_id) ? nextFilters.waba_id : "";
  const allowedPhoneIds = new Set<string>();
  for (const account of scopedAccounts) {
    if (resolvedWabaId && account.waba_id !== resolvedWabaId) {
      continue;
    }
    for (const phone of account.phone_numbers) {
      allowedPhoneIds.add(phone.phone_number_id);
    }
  }
  const resolvedPhoneId =
    nextFilters.phone_number_id && allowedPhoneIds.has(nextFilters.phone_number_id)
      ? nextFilters.phone_number_id
      : "";
  return {
    ...nextFilters,
    waba_id: resolvedWabaId,
    phone_number_id: resolvedPhoneId,
  };
}

export function WhatsAppStatsPage(): JSX.Element {
  const openWorkspacePage = useAppStore((state) => state.openWorkspacePage);
  const openAuditPage = useAppStore((state) => state.openAuditPage);
  const whatsappStatsPagePrefill = useAppStore((state) => state.whatsappStatsPagePrefill);
  const clearWhatsAppStatsPagePrefill = useAppStore((state) => state.clearWhatsAppStatsPagePrefill);
  const lastAppliedPrefillNonce = useRef<number | null>(null);

  const [metaAccounts, setMetaAccounts] = useState<MetaWabaAccount[]>([]);
  const [filters, setFilters] = useState<FilterDraft>(DEFAULT_FILTERS);
  const [summary, setSummary] = useState<WhatsAppStatsSummary>(EMPTY_SUMMARY);
  const [rows, setRows] = useState<WhatsAppStatsDailyRow[]>([]);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [rebuilding, setRebuilding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const accountMap = useMemo(
    () => new Map(metaAccounts.map((account) => [account.account_id, account])),
    [metaAccounts]
  );

  const accountOptions = useMemo(
    () =>
      Array.from(new Set(metaAccounts.map((account) => account.account_id))).sort((left, right) =>
        left.localeCompare(right)
      ),
    [metaAccounts]
  );

  const wabaOptions = useMemo(() => {
    const scopedAccounts = metaAccounts.filter((account) =>
      filters.account_id ? account.account_id === filters.account_id : true
    );
    return scopedAccounts
      .map((account) => ({
        waba_id: account.waba_id,
        label: `${account.display_name} / ${account.waba_id}`,
      }))
      .sort((left, right) => left.label.localeCompare(right.label));
  }, [filters.account_id, metaAccounts]);

  const phoneOptions = useMemo(() => {
    const values = new Set<string>();
    for (const account of metaAccounts) {
      if (filters.account_id && account.account_id !== filters.account_id) {
        continue;
      }
      if (filters.waba_id && account.waba_id !== filters.waba_id) {
        continue;
      }
      for (const phone of account.phone_numbers) {
        values.add(phone.phone_number_id);
      }
    }
    return Array.from(values).sort((left, right) => left.localeCompare(right));
  }, [filters.account_id, filters.waba_id, metaAccounts]);

  const byAccount = useMemo(() => groupRows(rows, (row) => row.account_id), [rows]);
  const byWaba = useMemo(() => groupRows(rows, (row) => row.waba_id), [rows]);
  const byPhone = useMemo(() => groupRows(rows, (row) => row.phone_number_id), [rows]);

  useEffect(() => {
    void loadStats(DEFAULT_FILTERS);
  }, []);

  useEffect(() => {
    if (!whatsappStatsPagePrefill) {
      return;
    }
    if (lastAppliedPrefillNonce.current === whatsappStatsPagePrefill.nonce) {
      return;
    }
    lastAppliedPrefillNonce.current = whatsappStatsPagePrefill.nonce;
    const nextFilters = toFilterDraft(whatsappStatsPagePrefill);
    setFilters(nextFilters);
    clearWhatsAppStatsPagePrefill();
    void loadStats(nextFilters);
  }, [clearWhatsAppStatsPagePrefill, whatsappStatsPagePrefill]);

  async function loadStats(activeFilters: FilterDraft = filters): Promise<void> {
    setRefreshing(true);
    setError(null);
    try {
      const params = toQueryParams(activeFilters);
      const [accounts, detail] = await Promise.all([
        listMetaAccounts(),
        getWhatsAppStatsDetail(params),
      ]);
      const normalizedFilters = normalizeScopedFilters(activeFilters, accounts);
      setMetaAccounts(accounts);
      setFilters(normalizedFilters);
      setSummary(detail.summary);
      setRows(detail.daily_rows);
      setLastUpdatedAt(detail.generated_at ?? new Date().toISOString());
    } catch (loadError) {
      setSummary(EMPTY_SUMMARY);
      setRows([]);
      setError(loadError instanceof Error ? loadError.message : "加载 WhatsApp 运营统计失败。");
    } finally {
      setRefreshing(false);
    }
  }

  async function handleRebuild(): Promise<void> {
    setRebuilding(true);
    setError(null);
    setNotice(null);
    try {
      const result = await rebuildWhatsAppStats(toQueryParams(filters));
      const accountLabel = result.account_id ? getAccountLabel(result.account_id, accountMap) : "全部账号";
      setNotice(
        `已重建统计：${accountLabel} / ${result.waba_id ?? "全部 WABA"} / ${result.phone_number_id ?? "全部号码"} / ${result.date_from ?? "不限开始"} ~ ${result.date_to ?? "不限结束"}`
      );
      await loadStats(filters);
    } catch (rebuildError) {
      setError(rebuildError instanceof Error ? rebuildError.message : "重建 WhatsApp 运营统计失败。");
    } finally {
      setRebuilding(false);
    }
  }

  function updateFilters(updater: (current: FilterDraft) => FilterDraft): void {
    setFilters((current) => normalizeScopedFilters(updater(current), metaAccounts));
  }

  return (
    <section className="grid">
      <Panel title="WhatsApp 运营统计">
        <p className="muted">
          按账号、WABA、Phone-Number-ID、会话来源和时间窗口查看运营数据，主要用于多账号后台排查和运营复盘。
        </p>
        {error ? <p className="status-error">{error}</p> : null}
        {notice ? <p className="status-note">{notice}</p> : null}

        <div className="dashboard-toolbar">
          <p className="muted">
            {lastUpdatedAt ? `上次刷新：${formatTimestamp(lastUpdatedAt)} / 当前 ${rows.length} 条明细` : "统计加载中..."}
          </p>
          <div className="meta-form-actions">
            <button className="seed-button seed-button-secondary" onClick={() => void loadStats()} type="button">
              {refreshing ? "刷新中..." : "刷新统计"}
            </button>
            <button className="seed-button" onClick={() => void handleRebuild()} type="button">
              {rebuilding ? "重建中..." : "重建统计"}
            </button>
          </div>
        </div>

        <div className="template-filter-row">
          <label>
            账号
            <select
              value={filters.account_id}
              onChange={(event) =>
                updateFilters((current) => ({
                  ...current,
                  account_id: event.target.value,
                }))
              }
            >
              <option value="">全部账号</option>
              {accountOptions.map((accountId) => (
                <option key={accountId} value={accountId}>
                  {getAccountLabel(accountId, accountMap)}
                </option>
              ))}
            </select>
          </label>

          <label>
            WABA
            <select
              value={filters.waba_id}
              onChange={(event) =>
                updateFilters((current) => ({
                  ...current,
                  waba_id: event.target.value,
                }))
              }
            >
              <option value="">全部 WABA</option>
              {wabaOptions.map((option) => (
                <option key={option.waba_id} value={option.waba_id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <label>
            Phone-Number-ID
            <select
              value={filters.phone_number_id}
              onChange={(event) =>
                updateFilters((current) => ({
                  ...current,
                  phone_number_id: event.target.value,
                }))
              }
            >
              <option value="">全部号码</option>
              {phoneOptions.map((phoneNumberId) => (
                <option key={phoneNumberId} value={phoneNumberId}>
                  {phoneNumberId}
                </option>
              ))}
            </select>
          </label>

          <label>
            来源
            <input
              value={filters.conversation_origin_type}
              onChange={(event) =>
                updateFilters((current) => ({
                  ...current,
                  conversation_origin_type: event.target.value,
                }))
              }
              placeholder="如 user_initiated / business_initiated"
            />
          </label>

          <label>
            会话类别
            <input
              value={filters.conversation_category}
              onChange={(event) =>
                updateFilters((current) => ({
                  ...current,
                  conversation_category: event.target.value,
                }))
              }
              placeholder="如 utility / marketing"
            />
          </label>

          <label>
            计费模型
            <input
              value={filters.pricing_model}
              onChange={(event) =>
                updateFilters((current) => ({
                  ...current,
                  pricing_model: event.target.value,
                }))
              }
              placeholder="如 CBP"
            />
          </label>

          <label>
            是否计费
            <select
              value={filters.billable}
              onChange={(event) =>
                updateFilters((current) => ({
                  ...current,
                  billable: event.target.value as "all" | "true" | "false",
                }))
              }
            >
              <option value="all">全部</option>
              <option value="true">仅计费</option>
              <option value="false">仅非计费</option>
            </select>
          </label>

          <label>
            小时桶
            <input
              type="number"
              max={23}
              min={0}
              value={filters.hour_bucket}
              onChange={(event) =>
                updateFilters((current) => ({
                  ...current,
                  hour_bucket: event.target.value,
                }))
              }
              placeholder="0 - 23"
            />
          </label>

          <label>
            开始日期
            <input
              type="date"
              value={filters.date_from}
              onChange={(event) =>
                updateFilters((current) => ({
                  ...current,
                  date_from: event.target.value,
                }))
              }
            />
          </label>

          <label>
            结束日期
            <input
              type="date"
              value={filters.date_to}
              onChange={(event) =>
                updateFilters((current) => ({
                  ...current,
                  date_to: event.target.value,
                }))
              }
            />
          </label>

          <div className="meta-form-actions">
            <button className="seed-button" onClick={() => void loadStats()} type="button">
              应用筛选
            </button>
            <button
              className="seed-button seed-button-secondary"
              onClick={() => {
                setFilters(DEFAULT_FILTERS);
                void loadStats(DEFAULT_FILTERS);
              }}
              type="button"
            >
              重置
            </button>
          </div>
        </div>

        <div className="template-summary-grid">
          <StatCard title="会话数" value={summary.conversation_count} description="统计窗口内覆盖的会话数" />
          <StatCard title="客户数" value={summary.unique_customer_count} description="去重后的客户数" />
          <StatCard title="入站消息" value={summary.inbound_message_count} description="用户发来的消息量" />
          <StatCard title="出站消息" value={summary.outbound_message_count} description="系统或人工发出的消息量" />
          <StatCard title="已送达" value={summary.delivered_count} description="provider returned delivered 的数量" />
          <StatCard title="已读" value={summary.read_count} description="provider returned read 的数量" />
          <StatCard title="失败" value={summary.failed_count} description="发送失败或失败回执数量" />
          <StatCard
            title="预估成本"
            value={formatCost(summary.estimated_cost)}
            description={summary.estimated_cost_note ?? "成本来自 provider 回执中的 estimated_cost"}
          />
        </div>
      </Panel>

      <Panel title="分布概览">
        <div className="template-summary-grid">
          <article className="template-summary-card">
            <strong>账号分布</strong>
            <span>{byAccount.length}</span>
            <p className="muted">按账号聚合</p>
          </article>
          <article className="template-summary-card">
            <strong>WABA 分布</strong>
            <span>{byWaba.length}</span>
            <p className="muted">按 WABA 聚合</p>
          </article>
          <article className="template-summary-card">
            <strong>号码分布</strong>
            <span>{byPhone.length}</span>
            <p className="muted">按 Phone-Number-ID 聚合</p>
          </article>
          <article className="template-summary-card">
            <strong>明细行数</strong>
            <span>{rows.length}</span>
            <p className="muted">当前筛选命中的日统计行</p>
          </article>
        </div>

        <div className="list" style={{ marginTop: 16 }}>
          {byAccount.slice(0, 8).map((row) => (
            <article className="panel panel-subtle" key={`account:${row.key}`}>
              <div className="toolbar">
                <strong>{getAccountLabel(row.key, accountMap)}</strong>
                <span>{`出站 ${row.outbound_message_count}`}</span>
                <span>{`入站 ${row.inbound_message_count}`}</span>
              </div>
              <p className="muted">{`送达 ${row.delivered_count} / 已读 ${row.read_count} / 失败 ${row.failed_count} / 成本 ${formatCost(row.estimated_cost)}`}</p>
              <div className="meta-form-actions">
                <button
                  className="seed-button seed-button-secondary"
                  onClick={() => openWorkspacePage({ accountId: row.key })}
                  type="button"
                >
                  打开工作台
                </button>
                <button
                  className="seed-button seed-button-secondary"
                  onClick={() => openAuditPage({ account_id: row.key, limit: 50 })}
                  type="button"
                >
                  查看审计
                </button>
              </div>
            </article>
          ))}
        </div>
      </Panel>

      <Panel title="日统计明细">
        <div className="list">
          {rows.map((row, index) => (
            <article
              className="panel panel-subtle"
              key={`${row.account_id}:${row.date}:${row.phone_number_id ?? "account"}:${index}`}
            >
              <div className="toolbar">
                <strong>{`${getAccountLabel(row.account_id, accountMap)} / ${row.waba_id ?? "未绑定 WABA"}`}</strong>
                <span>{row.date}</span>
                <span>{row.phone_number_id ?? "账号级聚合"}</span>
              </div>
              <p className="muted">
                {`小时 ${formatHourBucket(row.hour_bucket)} / 入站 ${row.inbound_message_count} / 出站 ${row.outbound_message_count} / 送达 ${row.delivered_count} / 已读 ${row.read_count} / 失败 ${row.failed_count}`}
              </p>
              <p className="muted">
                {`来源 ${formatDimensionValue(row.conversation_origin_type, "未标记")} / 类别 ${formatDimensionValue(row.conversation_category, "未标记")} / 计费模型 ${formatDimensionValue(row.pricing_model, "未标记")} / ${formatBillable(row.billable)} / 成本 ${formatCost(row.estimated_cost)}`}
              </p>
              <div className="meta-form-actions">
                <button
                  className="seed-button seed-button-secondary"
                  onClick={() =>
                    openWorkspacePage({
                      accountId: row.account_id,
                      wabaId: row.waba_id ?? undefined,
                      phoneNumberId: row.phone_number_id ?? undefined,
                    })
                  }
                  type="button"
                >
                  打开工作台
                </button>
                <button
                  className="seed-button seed-button-secondary"
                  onClick={() =>
                    openAuditPage({
                      account_id: row.account_id,
                      waba_id: row.waba_id ?? undefined,
                      phone_number_id: row.phone_number_id ?? undefined,
                      limit: 50,
                    })
                  }
                  type="button"
                >
                  查看审计
                </button>
              </div>
            </article>
          ))}
          {rows.length === 0 ? <p className="muted">当前筛选范围内没有 WhatsApp 运营统计明细。</p> : null}
        </div>
      </Panel>
    </section>
  );
}
