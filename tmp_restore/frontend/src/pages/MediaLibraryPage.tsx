import { useEffect, useMemo, useState, type FormEvent, type JSX } from "react";

import { Panel } from "../components/Panel";
import { useAppStore } from "../stores/appStore";
import {
  createMediaAsset,
  getMediaAssetDetail,
  isApiFeatureUnavailable,
  listMediaAssets,
  listMetaAccounts,
  sendConversationMediaMessage,
  syncMediaAsset,
  updateMediaAsset,
  uploadMediaAsset,
  type MediaAssetDetailResponse,
  type MediaAssetSendResponse,
  type MediaAssetSyncResponse,
  type MediaAssetType,
  type MediaAssetView,
  type MetaWabaAccount,
} from "../services/api";

type MediaFilters = {
  account_id: string;
  waba_id: string;
  phone_number_id: string;
  asset_type: "ALL" | MediaAssetType;
  is_active: "all" | "true" | "false";
  query: string;
  tag: string;
};

type MediaAssetFormState = {
  account_id: string;
  waba_id: string;
  phone_number_id: string;
  name: string;
  asset_type: MediaAssetType;
  mime_type: string;
  storage_key: string;
  storage_url: string;
  provider_media_id: string;
  tags_text: string;
};

type UploadFormState = {
  account_id: string;
  waba_id: string;
  phone_number_id: string;
  name: string;
  source: string;
  tags_text: string;
};

type EditFormState = {
  name: string;
  waba_id: string;
  phone_number_id: string;
  tags_text: string;
  is_active: "true" | "false";
};

type SyncFormState = {
  phone_number_id: string;
  force_resync: boolean;
};

type SendFormState = {
  account_id: string;
  conversation_id: string;
  asset_id: string;
  caption: string;
  file_name: string;
  agent_id: string;
};

const DEFAULT_ACCOUNT_ID = "demo-account-cn";

const INITIAL_FILTERS: MediaFilters = {
  account_id: "ALL",
  waba_id: "ALL",
  phone_number_id: "ALL",
  asset_type: "ALL",
  is_active: "true",
  query: "",
  tag: "",
};

const INITIAL_CREATE_FORM: MediaAssetFormState = {
  account_id: DEFAULT_ACCOUNT_ID,
  waba_id: "",
  phone_number_id: "",
  name: "shipping-banner",
  asset_type: "image",
  mime_type: "image/jpeg",
  storage_key: "",
  storage_url: "https://cdn.example.com/shipping-banner.jpg",
  provider_media_id: "",
  tags_text: "shipping,banner",
};

const INITIAL_UPLOAD_FORM: UploadFormState = {
  account_id: DEFAULT_ACCOUNT_ID,
  waba_id: "",
  phone_number_id: "",
  name: "",
  source: "upload",
  tags_text: "",
};

function formatTimestamp(value: string | null): string {
  if (!value) {
    return "未记录";
  }
  return new Date(value).toLocaleString("zh-CN");
}

function formatOptionalText(value: string | null | undefined, fallback = "未设置"): string {
  return value && value.trim() ? value : fallback;
}

function formatConversationText(value: string | null | undefined): string {
  return formatOptionalText(value, "未关联");
}

function formatAccountLabel(accountId: string, accountMap: Map<string, MetaWabaAccount>): string {
  const account = accountMap.get(accountId);
  return account ? `${account.display_name} (${accountId})` : accountId;
}

function formatAssetType(assetType: MediaAssetType): string {
  if (assetType === "image") {
    return "图片";
  }
  if (assetType === "audio") {
    return "音频";
  }
  if (assetType === "video") {
    return "视频";
  }
  return "文档";
}

function formatSyncStatus(status: string): string {
  if (status === "synced") {
    return "已同步";
  }
  if (status === "reused") {
    return "复用";
  }
  if (status === "linked") {
    return "已绑定";
  }
  if (status === "failed") {
    return "失败";
  }
  return status;
}

function getSyncBadgeClass(status: string): string {
  if (status === "synced" || status === "linked" || status === "reused") {
    return "badge badge-success";
  }
  if (status === "failed") {
    return "badge badge-warning";
  }
  return "badge badge-neutral";
}

function getAssetBadgeClass(asset: MediaAssetView): string {
  if (!asset.is_active) {
    return "badge badge-muted";
  }
  if (asset.meta_media_id || asset.provider_references.length > 0) {
    return "badge badge-success";
  }
  return "badge badge-neutral";
}

function getDistinctLegacyMetaMediaId(
  providerMediaId: string | null | undefined,
  legacyMetaMediaId: string | null | undefined
): string | null {
  if (!legacyMetaMediaId || legacyMetaMediaId === providerMediaId) {
    return null;
  }
  return legacyMetaMediaId;
}

function getPreferredProviderReference(
  asset: MediaAssetView | null,
  phoneNumberId: string | null | undefined,
  providerReferences: MediaAssetDetailResponse["provider_syncs"] | MediaAssetView["provider_references"]
): MediaAssetDetailResponse["provider_syncs"][number] | MediaAssetView["provider_references"][number] | null {
  if (providerReferences.length === 0) {
    return null;
  }
  if (phoneNumberId) {
    return providerReferences.find((sync) => sync.phone_number_id === phoneNumberId) ?? providerReferences[0];
  }
  if (asset?.phone_number_id) {
    return (
      providerReferences.find((sync) => sync.phone_number_id === asset.phone_number_id) ??
      providerReferences[0]
    );
  }
  return providerReferences[0];
}

function getProviderReferenceValue(
  reference:
    | Pick<MediaAssetDetailResponse["provider_syncs"][number], "provider_media_id" | "meta_media_id">
    | null
    | undefined
): string | null {
  return reference?.provider_media_id ?? reference?.meta_media_id ?? null;
}

function getAssetPrimaryProviderReference(asset: MediaAssetView): string | null {
  const scopedReference =
    asset.provider_references.find((reference) => reference.phone_number_id === asset.phone_number_id) ??
    asset.provider_references[0] ??
    null;
  return getProviderReferenceValue(scopedReference) ?? asset.meta_media_id;
}

function getLegacyMetaMediaId(asset: MediaAssetView): string | null {
  return getDistinctLegacyMetaMediaId(
    getAssetPrimaryProviderReference(asset),
    asset.legacy_meta_media_id ?? asset.meta_media_id
  );
}

function parseTags(input: string): string[] {
  return input
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function toOptionalString(value: string): string | undefined {
  return value.trim() ? value.trim() : undefined;
}

function inferAssetType(file: File): MediaAssetType {
  if (file.type.startsWith("image/")) {
    return "image";
  }
  if (file.type.startsWith("audio/")) {
    return "audio";
  }
  if (file.type.startsWith("video/")) {
    return "video";
  }
  return "document";
}

function toEditForm(asset: MediaAssetView | null): EditFormState {
  return {
    name: asset?.name ?? "",
    waba_id: asset?.waba_id ?? "",
    phone_number_id: asset?.phone_number_id ?? "",
    tags_text: asset?.tags.join(",") ?? "",
    is_active: asset?.is_active === false ? "false" : "true",
  };
}

function getPhoneOptions(accounts: MetaWabaAccount[], accountId: string, wabaId: string): string[] {
  const values = new Set<string>();
  for (const account of accounts) {
    if (accountId !== "ALL" && account.account_id !== accountId) {
      continue;
    }
    if (wabaId !== "ALL" && account.waba_id !== wabaId) {
      continue;
    }
    for (const phone of account.phone_numbers) {
      values.add(phone.phone_number_id);
    }
  }
  return Array.from(values).sort();
}

function buildListParams(filters: MediaFilters): {
  account_id?: string;
  waba_id?: string;
  phone_number_id?: string;
  asset_type?: MediaAssetType;
  is_active?: boolean;
  query?: string;
  tag?: string;
} {
  return {
    ...(filters.account_id !== "ALL" ? { account_id: filters.account_id } : {}),
    ...(filters.waba_id !== "ALL" ? { waba_id: filters.waba_id } : {}),
    ...(filters.phone_number_id !== "ALL" ? { phone_number_id: filters.phone_number_id } : {}),
    ...(filters.asset_type !== "ALL" ? { asset_type: filters.asset_type } : {}),
    ...(filters.is_active === "true"
      ? { is_active: true }
      : filters.is_active === "false"
        ? { is_active: false }
        : {}),
    ...(filters.query.trim() ? { query: filters.query.trim() } : {}),
    ...(filters.tag.trim() ? { tag: filters.tag.trim() } : {}),
  };
}

function renderPreview(detail: MediaAssetDetailResponse | null): JSX.Element | null {
  const asset = detail?.asset;
  if (!asset?.storage_url) {
    return <p className="muted">当前资源没有可预览的存储地址。</p>;
  }
  if (asset.asset_type === "image") {
    return (
      <img
        alt={asset.name}
        src={asset.storage_url}
        style={{ width: "100%", maxHeight: 220, objectFit: "cover", borderRadius: 8 }}
      />
    );
  }
  if (asset.asset_type === "audio") {
    return <audio controls src={asset.storage_url} style={{ width: "100%" }} />;
  }
  if (asset.asset_type === "video") {
    return (
      <video
        controls
        src={asset.storage_url}
        style={{ width: "100%", maxHeight: 240, borderRadius: 8 }}
      />
    );
  }
  return (
    <a href={asset.storage_url} rel="noreferrer" target="_blank">
      打开原始文件
    </a>
  );
}

export function MediaLibraryPage(): JSX.Element {
  const openWorkspacePage = useAppStore((state) => state.openWorkspacePage);

  const [accounts, setAccounts] = useState<MetaWabaAccount[]>([]);
  const [assets, setAssets] = useState<MediaAssetView[]>([]);
  const [filters, setFilters] = useState<MediaFilters>(INITIAL_FILTERS);
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);
  const [selectedAssetDetail, setSelectedAssetDetail] = useState<MediaAssetDetailResponse | null>(null);
  const [createForm, setCreateForm] = useState<MediaAssetFormState>(INITIAL_CREATE_FORM);
  const [uploadForm, setUploadForm] = useState<UploadFormState>(INITIAL_UPLOAD_FORM);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [editForm, setEditForm] = useState<EditFormState>(toEditForm(null));
  const [syncForm, setSyncForm] = useState<SyncFormState>({
    phone_number_id: "",
    force_resync: false,
  });
  const [sendForm, setSendForm] = useState<SendFormState>({
    account_id: DEFAULT_ACCOUNT_ID,
    conversation_id: "",
    asset_id: "",
    caption: "",
    file_name: "",
    agent_id: "",
  });
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<string | null>(null);
  const [lastSendResult, setLastSendResult] = useState<MediaAssetSendResponse | null>(null);
  const [lastSyncResult, setLastSyncResult] = useState<MediaAssetSyncResponse | null>(null);

  const accountMap = useMemo(
    () => new Map(accounts.map((account) => [account.account_id, account])),
    [accounts]
  );
  const accountOptions = useMemo(
    () => Array.from(new Set(accounts.map((account) => account.account_id))).sort((left, right) => left.localeCompare(right)),
    [accounts]
  );

  const selectedAsset = useMemo(
    () => assets.find((asset) => asset.asset_id === selectedAssetId) ?? null,
    [assets, selectedAssetId]
  );
  const lastSendExternalConversationId = useMemo(
    () => (lastSendResult ? toOptionalString(lastSendResult.external_conversation_id ?? "") ?? null : null),
    [lastSendResult]
  );

  const wabaOptions = useMemo(() => {
    const values = new Set<string>();
    for (const account of accounts) {
      if (filters.account_id === "ALL" || account.account_id === filters.account_id) {
        values.add(account.waba_id);
      }
    }
    return Array.from(values).sort();
  }, [accounts, filters.account_id]);

  const phoneOptions = useMemo(
    () => getPhoneOptions(accounts, filters.account_id, filters.waba_id),
    [accounts, filters.account_id, filters.waba_id]
  );

  const createPhoneOptions = useMemo(
    () =>
      getPhoneOptions(
        accounts,
        createForm.account_id || "ALL",
        createForm.waba_id || "ALL"
      ),
    [accounts, createForm.account_id, createForm.waba_id]
  );

  const uploadPhoneOptions = useMemo(
    () =>
      getPhoneOptions(
        accounts,
        uploadForm.account_id || "ALL",
        uploadForm.waba_id || "ALL"
      ),
    [accounts, uploadForm.account_id, uploadForm.waba_id]
  );

  const detailPhoneOptions = useMemo(
    () =>
      getPhoneOptions(
        accounts,
        selectedAsset?.account_id ?? "ALL",
        selectedAsset?.waba_id ?? "ALL"
      ),
    [accounts, selectedAsset?.account_id, selectedAsset?.waba_id]
  );

  useEffect(() => {
    void refreshAssets();
  }, [
    filters.account_id,
    filters.waba_id,
    filters.phone_number_id,
    filters.asset_type,
    filters.is_active,
    filters.query,
    filters.tag,
  ]);

  useEffect(() => {
    if (assets.length === 0) {
      setSelectedAssetId(null);
      return;
    }
    if (!selectedAssetId || !assets.some((asset) => asset.asset_id === selectedAssetId)) {
      setSelectedAssetId(assets[0].asset_id);
    }
  }, [assets, selectedAssetId]);

  useEffect(() => {
    if (!selectedAssetId) {
      setSelectedAssetDetail(null);
      return;
    }
    void refreshAssetDetail(selectedAssetId);
  }, [selectedAssetId]);

  useEffect(() => {
    setEditForm(toEditForm(selectedAsset));
    setSyncForm({
      phone_number_id: selectedAsset?.phone_number_id ?? "",
      force_resync: false,
    });
    setSendForm((current) => ({
      ...current,
      account_id: selectedAsset?.account_id ?? DEFAULT_ACCOUNT_ID,
      asset_id: selectedAsset?.asset_id ?? "",
    }));
    setLastSendResult(null);
    setLastSyncResult(null);
  }, [selectedAsset]);

  async function refreshAssets(): Promise<void> {
    setRefreshing(true);
    setError(null);
    const nextWarnings: string[] = [];

    const [accountResult, assetResult] = await Promise.allSettled([
      listMetaAccounts(),
      listMediaAssets(buildListParams(filters)),
    ]);

    if (accountResult.status === "fulfilled") {
      setAccounts(accountResult.value);
    } else {
      nextWarnings.push("Meta 账号列表加载失败，筛选项暂时不可用。");
      setAccounts([]);
    }

    if (assetResult.status === "fulfilled") {
      setAssets(assetResult.value);
    } else if (isApiFeatureUnavailable(assetResult.reason)) {
      setAssets([]);
      setError("媒体库接口暂未就绪，请先接通后端接口或使用 mock 数据。");
    } else {
      setAssets([]);
      setError("媒体资源列表加载失败，请稍后重试。");
    }

    setWarnings(nextWarnings);
    setLastUpdatedAt(new Date().toISOString());
    setRefreshing(false);
  }

  async function refreshAssetDetail(assetId: string): Promise<void> {
    try {
      const detail = await getMediaAssetDetail(assetId);
      setSelectedAssetDetail(detail);
    } catch (fetchError) {
      if (isApiFeatureUnavailable(fetchError)) {
        setWarnings((current) => Array.from(new Set([...current, "媒体详情接口暂未就绪。"])));
      } else {
        setWarnings((current) => Array.from(new Set([...current, "媒体详情加载失败，请稍后重试。"])));
      }
      setSelectedAssetDetail(null);
    }
  }

  async function handleCreateAsset(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setPendingAction("create-asset");
    setError(null);
    setNotice(null);
    try {
      const created = await createMediaAsset({
        account_id: createForm.account_id,
        waba_id: toOptionalString(createForm.waba_id),
        phone_number_id: toOptionalString(createForm.phone_number_id),
        name: createForm.name.trim(),
        asset_type: createForm.asset_type,
        mime_type: createForm.mime_type.trim(),
        storage_key: toOptionalString(createForm.storage_key),
        storage_url: toOptionalString(createForm.storage_url),
        provider_media_id: toOptionalString(createForm.provider_media_id),
        tags: parseTags(createForm.tags_text),
        source: "manual",
      });
      setNotice(`媒体资源 ${created.name} 已创建。`);
      setSelectedAssetId(created.asset_id);
      await refreshAssets();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "创建媒体资源失败，请检查表单后重试。");
    } finally {
      setPendingAction(null);
    }
  }

  async function handleUploadAsset(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!uploadFile) {
      setError("请先选择要上传的文件。");
      return;
    }
    setPendingAction("upload-asset");
    setError(null);
    setNotice(null);
    try {
      const uploaded = await uploadMediaAsset({
        account_id: uploadForm.account_id,
        waba_id: toOptionalString(uploadForm.waba_id),
        phone_number_id: toOptionalString(uploadForm.phone_number_id),
        name: toOptionalString(uploadForm.name),
        source: toOptionalString(uploadForm.source),
        tags: parseTags(uploadForm.tags_text),
        file: uploadFile,
        asset_type: inferAssetType(uploadFile),
        mime_type: uploadFile.type || undefined,
      });
      setNotice(`媒体资源 ${uploaded.name} 已上传。`);
      setSelectedAssetId(uploaded.asset_id);
      setUploadFile(null);
      await refreshAssets();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "上传媒体资源失败，请稍后重试。");
    } finally {
      setPendingAction(null);
    }
  }

  async function handleUpdateAsset(): Promise<void> {
    if (!selectedAsset) {
      return;
    }
    setPendingAction("update-asset");
    setError(null);
    setNotice(null);
    try {
      const updated = await updateMediaAsset(selectedAsset.asset_id, {
        name: editForm.name.trim(),
        waba_id: toOptionalString(editForm.waba_id) ?? null,
        phone_number_id: toOptionalString(editForm.phone_number_id) ?? null,
        tags: parseTags(editForm.tags_text),
        is_active: editForm.is_active === "true",
      });
      setNotice(`媒体资源 ${updated.name} 已更新。`);
      setSelectedAssetId(updated.asset_id);
      await refreshAssets();
      await refreshAssetDetail(updated.asset_id);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "更新媒体资源失败，请稍后重试。");
    } finally {
      setPendingAction(null);
    }
  }

  async function handleSyncAsset(): Promise<void> {
    if (!selectedAsset) {
      return;
    }
    setPendingAction("sync-asset");
    setError(null);
    setNotice(null);
    try {
      const result = await syncMediaAsset(selectedAsset.asset_id, {
        phone_number_id: toOptionalString(syncForm.phone_number_id),
        force_resync: syncForm.force_resync,
      });
      setLastSyncResult(result);
      setNotice(`资源 ${selectedAsset.name} 已完成同步，当前状态：${formatSyncStatus(result.sync_status)}。`);
      await refreshAssets();
      await refreshAssetDetail(selectedAsset.asset_id);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "同步媒体资源失败，请稍后重试。");
    } finally {
      setPendingAction(null);
    }
  }

  async function handleSendAsset(): Promise<void> {
    if (!selectedAsset) {
      return;
    }
    setPendingAction("send-asset");
    setError(null);
    setNotice(null);
    try {
      const result = await sendConversationMediaMessage(
        sendForm.account_id,
        sendForm.conversation_id.trim(),
        {
          asset_id: selectedAsset.asset_id,
          caption: toOptionalString(sendForm.caption),
          file_name: toOptionalString(sendForm.file_name),
          agent_id: toOptionalString(sendForm.agent_id),
        }
      );
      setLastSendResult(result);
      setNotice(`媒体资源 ${selectedAsset.name} 已发送到外部会话 ${result.external_conversation_id}。`);
      await refreshAssetDetail(selectedAsset.asset_id);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "发送媒体资源失败，请稍后重试。");
    } finally {
      setPendingAction(null);
    }
  }

  return (
    <Panel title="媒体资源库">
      <section className="dashboard-section">
        <article className="settings-card">
          <div className="settings-card-header">
            <div>
              <strong>媒体总览</strong>
              <p className="muted">
                媒体资源按账号、WABA、Phone-Number-ID 作用域归档，可复用于模板头部、会话发送和后续正式接入联调。
              </p>
            </div>
            <span className="badge badge-neutral">
              {refreshing ? "刷新中..." : `共 ${assets.length} 条`}
            </span>
          </div>

          {error ? <p className="status-error">{error}</p> : null}
          {notice ? <p className="status-ok">{notice}</p> : null}
          {warnings.map((warning) => (
            <p className="info-banner" key={warning}>
              {warning}
            </p>
          ))}

          <div className="meta-form">
            <label>
              账号
              <select
                value={filters.account_id}
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    account_id: event.target.value,
                    waba_id: "ALL",
                    phone_number_id: "ALL",
                  }))
                }
              >
                <option value="ALL">全部账号</option>
                {accountOptions.map((accountId) => (
                  <option key={accountId} value={accountId}>
                    {formatAccountLabel(accountId, accountMap)}
                  </option>
                ))}
              </select>
            </label>

            <label>
              WABA
              <select
                value={filters.waba_id}
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    waba_id: event.target.value,
                    phone_number_id: "ALL",
                  }))
                }
              >
                <option value="ALL">全部 WABA</option>
                {wabaOptions.map((wabaId) => (
                  <option key={wabaId} value={wabaId}>
                    {wabaId}
                  </option>
                ))}
              </select>
            </label>

            <label>
              Phone-Number-ID
              <select
                value={filters.phone_number_id}
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    phone_number_id: event.target.value,
                  }))
                }
              >
                <option value="ALL">全部号码</option>
                {phoneOptions.map((phoneNumberId) => (
                  <option key={phoneNumberId} value={phoneNumberId}>
                    {phoneNumberId}
                  </option>
                ))}
              </select>
            </label>

            <label>
              资源类型
              <select
                value={filters.asset_type}
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    asset_type: event.target.value as "ALL" | MediaAssetType,
                  }))
                }
              >
                <option value="ALL">全部类型</option>
                <option value="image">图片</option>
                <option value="audio">音频</option>
                <option value="video">视频</option>
                <option value="document">文档</option>
              </select>
            </label>

            <label>
              资源状态
              <select
                value={filters.is_active}
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    is_active: event.target.value as "all" | "true" | "false",
                  }))
                }
              >
                <option value="all">全部状态</option>
                <option value="true">仅启用</option>
                <option value="false">仅停用</option>
              </select>
            </label>

            <label>
              名称关键字
              <input
                value={filters.query}
                onChange={(event) =>
                  setFilters((current) => ({ ...current, query: event.target.value }))
                }
                placeholder="按名称搜索"
              />
            </label>

            <label>
              标签
              <input
                value={filters.tag}
                onChange={(event) =>
                  setFilters((current) => ({ ...current, tag: event.target.value }))
                }
                placeholder="如 shipping"
              />
            </label>
          </div>

          <p className="muted">最近刷新时间：{formatTimestamp(lastUpdatedAt)}</p>
        </article>
      </section>

      <section className="dashboard-section" style={{ display: "grid", gap: 16, gridTemplateColumns: "1.05fr 1.45fr" }}>
        <article className="settings-card">
          <div className="settings-card-header">
            <div>
              <strong>资源列表</strong>
              <p className="muted">优先确认资源是否已绑定到对应的 WABA 和 Phone-Number-ID。</p>
            </div>
          </div>

          <div className="template-list">
            {assets.map((asset) => (
              <button
                key={asset.asset_id}
                className="template-list-item"
                onClick={() => setSelectedAssetId(asset.asset_id)}
                style={{
                  display: "block",
                  width: "100%",
                  textAlign: "left",
                  border:
                    selectedAssetId === asset.asset_id
                      ? "1px solid var(--accent, #2563eb)"
                      : "1px solid rgba(148, 163, 184, 0.35)",
                  borderRadius: 8,
                  background: "transparent",
                  padding: 12,
                  marginBottom: 10,
                }}
                type="button"
              >
                <div className="template-card-header">
                  <strong>{asset.name}</strong>
                  <span className={getAssetBadgeClass(asset)}>
                    {asset.is_active ? "已启用" : "已停用"}
                  </span>
                </div>
                <div className="template-detail-grid">
                  <span>{formatAccountLabel(asset.account_id, accountMap)}</span>
                  <span>{asset.waba_id ?? "未绑定 WABA"}</span>
                  <span>{asset.phone_number_id ?? "未绑定号码"}</span>
                  <span>{formatAssetType(asset.asset_type)}</span>
                </div>
                <p className="muted">{asset.tags.length > 0 ? asset.tags.join(", ") : "未设置标签"}</p>
              </button>
            ))}
            {assets.length === 0 ? <p className="muted">当前筛选条件下没有媒体资源。</p> : null}
          </div>
        </article>

        <article className="settings-card">
          <div className="settings-card-header">
            <div>
              <strong>资源详情</strong>
              <p className="muted">
                在这里查看同步状态、使用情况和发送记录。资源详情优先展示当前号码命中的
                Provider 引用；Legacy Meta Media ID 仅保留为兼容字段。
              </p>
            </div>
          </div>

          {!selectedAsset ? (
            <p className="muted">请先从左侧选择一条媒体资源。</p>
          ) : (
            <>
              <div className="template-detail-grid">
                <span>{`资源 ID：${selectedAsset.asset_id}`}</span>
                <span>{`账号：${formatAccountLabel(selectedAsset.account_id, accountMap)}`}</span>
                <span>{`WABA ID：${formatOptionalText(selectedAsset.waba_id)}`}</span>
                <span>{`Phone-Number-ID：${formatOptionalText(selectedAsset.phone_number_id)}`}</span>
                <span>{`类型：${formatAssetType(selectedAsset.asset_type)}`}</span>
                <span>{`MIME：${selectedAsset.mime_type}`}</span>
                <span>{`Provider 引用（当前号码）：${formatOptionalText(getAssetPrimaryProviderReference(selectedAsset))}`}</span>
                <span>{`Legacy Meta Media ID（兼容字段）：${formatOptionalText(getLegacyMetaMediaId(selectedAsset))}`}</span>
                <span>{`最近更新：${formatTimestamp(selectedAsset.updated_at)}`}</span>
              </div>

              <div className="template-preview-block" style={{ marginTop: 12 }}>
                <strong>资源预览</strong>
                <div style={{ marginTop: 10 }}>{renderPreview(selectedAssetDetail)}</div>
              </div>

              <div className="template-preview-block" style={{ marginTop: 12 }}>
                <strong>更新资源</strong>
                <div className="meta-form">
                  <label>
                    名称
                    <input
                      value={editForm.name}
                      onChange={(event) =>
                        setEditForm((current) => ({ ...current, name: event.target.value }))
                      }
                    />
                  </label>

                  <label>
                    WABA
                    <input
                      value={editForm.waba_id}
                      onChange={(event) =>
                        setEditForm((current) => ({ ...current, waba_id: event.target.value }))
                      }
                    />
                  </label>

                  <label>
                    Phone-Number-ID
                    <select
                      value={editForm.phone_number_id}
                      onChange={(event) =>
                        setEditForm((current) => ({
                          ...current,
                          phone_number_id: event.target.value,
                        }))
                      }
                    >
                      <option value="">不限定号码</option>
                      {detailPhoneOptions.map((phoneNumberId) => (
                        <option key={phoneNumberId} value={phoneNumberId}>
                          {phoneNumberId}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label>
                    启用状态
                    <select
                      value={editForm.is_active}
                      onChange={(event) =>
                        setEditForm((current) => ({
                          ...current,
                          is_active: event.target.value as "true" | "false",
                        }))
                      }
                    >
                      <option value="true">启用</option>
                      <option value="false">停用</option>
                    </select>
                  </label>

                  <label className="meta-form-span-2">
                    标签
                    <input
                      value={editForm.tags_text}
                      onChange={(event) =>
                        setEditForm((current) => ({ ...current, tags_text: event.target.value }))
                      }
                      placeholder="多个标签用逗号分隔"
                    />
                  </label>

                  <div className="meta-form-actions meta-form-span-2">
                    <button
                      className="seed-button seed-button-secondary"
                      disabled={pendingAction !== null}
                      onClick={() => void handleUpdateAsset()}
                      type="button"
                    >
                      {pendingAction === "update-asset" ? "保存中..." : "保存更改"}
                    </button>
                  </div>
                </div>
              </div>

              <div className="template-preview-block" style={{ marginTop: 12 }}>
                <strong>同步到 Provider</strong>
                <div className="meta-form">
                  <label>
                    Phone-Number-ID
                    <select
                      value={syncForm.phone_number_id}
                      onChange={(event) =>
                        setSyncForm((current) => ({
                          ...current,
                          phone_number_id: event.target.value,
                        }))
                      }
                    >
                      <option value="">留空则沿用当前资源的 Phone-Number-ID</option>
                      {detailPhoneOptions.map((phoneNumberId) => (
                        <option key={phoneNumberId} value={phoneNumberId}>
                          {phoneNumberId}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label>
                    强制重新同步
                    <select
                      value={syncForm.force_resync ? "true" : "false"}
                      onChange={(event) =>
                        setSyncForm((current) => ({
                          ...current,
                          force_resync: event.target.value === "true",
                        }))
                      }
                    >
                      <option value="false">否</option>
                      <option value="true">是</option>
                    </select>
                  </label>

                  <div className="meta-form-actions meta-form-span-2">
                    <button
                      className="seed-button seed-button-secondary"
                      disabled={pendingAction !== null}
                      onClick={() => void handleSyncAsset()}
                      type="button"
                    >
                      {pendingAction === "sync-asset" ? "同步中..." : "开始同步"}
                    </button>
                  </div>
                </div>

                {lastSyncResult ? (
                  <div className="template-detail-grid" style={{ marginTop: 10 }}>
                    <span>{`同步通道：${lastSyncResult.provider_name}`}</span>
                    <span>{`WABA ID：${formatOptionalText(lastSyncResult.waba_id)}`}</span>
                    <span>{`Phone-Number-ID：${formatOptionalText(lastSyncResult.phone_number_id)}`}</span>
                    <span>{`Provider 引用（当前号码）：${formatOptionalText(getProviderReferenceValue(lastSyncResult))}`}</span>
                    <span>{`Legacy Meta Media ID（兼容字段）：${formatOptionalText(lastSyncResult.meta_media_id)}`}</span>
                    <span className={getSyncBadgeClass(lastSyncResult.sync_status)}>
                      {formatSyncStatus(lastSyncResult.sync_status)}
                    </span>
                  </div>
                ) : null}
              </div>

              <div className="template-preview-block" style={{ marginTop: 12 }}>
                <strong>发送到会话</strong>
                <p className="muted" style={{ marginTop: 10 }}>
                  这里填写外部会话 ID。发送结果会同时展示外部会话 ID 和内部会话 ID，
                  工作台“打开会话”继续按外部会话 ID 跳转。
                </p>
                <div className="meta-form">
                  <label>
                    账号
                    <input
                      value={sendForm.account_id}
                      onChange={(event) =>
                        setSendForm((current) => ({ ...current, account_id: event.target.value }))
                      }
                    />
                  </label>

                  <label>
                    外部会话 ID
                    <input
                      value={sendForm.conversation_id}
                      onChange={(event) =>
                        setSendForm((current) => ({
                          ...current,
                          conversation_id: event.target.value,
                        }))
                      }
                      placeholder="例如 conv-media-1"
                    />
                  </label>

                  <label>
                    附言
                    <input
                      value={sendForm.caption}
                      onChange={(event) =>
                        setSendForm((current) => ({ ...current, caption: event.target.value }))
                      }
                    />
                  </label>

                  <label>
                    出站文件名
                    <input
                      value={sendForm.file_name}
                      onChange={(event) =>
                        setSendForm((current) => ({ ...current, file_name: event.target.value }))
                      }
                      placeholder="可选，用于覆盖默认文件名"
                    />
                  </label>

                  <label className="meta-form-span-2">
                    发送人 ID
                    <input
                      value={sendForm.agent_id}
                      onChange={(event) =>
                        setSendForm((current) => ({ ...current, agent_id: event.target.value }))
                      }
                      placeholder="人工接管场景可填写 agent_id"
                    />
                  </label>

                  <div className="meta-form-actions meta-form-span-2">
                    <button
                      className="seed-button"
                      disabled={pendingAction !== null || !sendForm.conversation_id.trim()}
                      onClick={() => void handleSendAsset()}
                      type="button"
                    >
                      {pendingAction === "send-asset" ? "发送中..." : "发送媒体"}
                    </button>
                  </div>
                </div>

                {lastSendResult ? (
                  <>
                    <div className="template-detail-grid" style={{ marginTop: 10 }}>
                      <span>{`消息类型：${formatAssetType(lastSendResult.message_type)}`}</span>
                      <span>{`发送通道：${formatOptionalText(lastSendResult.provider)}`}</span>
                      <span>{`外部会话 ID：${formatConversationText(lastSendResult.external_conversation_id)}`}</span>
                      <span>{`内部会话 ID：${formatConversationText(lastSendResult.internal_conversation_id)}`}</span>
                      <span>{`消息 ID：${lastSendResult.message_id}`}</span>
                      <span>{`Provider 消息 ID：${formatOptionalText(lastSendResult.provider_message_id)}`}</span>
                      <span>{`Phone-Number-ID：${formatOptionalText(lastSendResult.phone_number_id)}`}</span>
                      <span>{`已翻译：${lastSendResult.translated ? "是" : "否"}`}</span>
                    </div>
                    <p className="muted" style={{ marginTop: 10 }}>
                      “打开会话”使用外部会话 ID；内部会话 ID 仅用于系统内排障和追踪。
                    </p>
                    <div className="meta-form-actions" style={{ marginTop: 10 }}>
                      {lastSendExternalConversationId ? (
                        <button
                          className="seed-button seed-button-secondary"
                          onClick={() =>
                            openWorkspacePage({
                              accountId: lastSendResult.account_id,
                              conversationKey: `${lastSendResult.account_id}:${lastSendExternalConversationId}`,
                            })
                          }
                          type="button"
                        >
                          打开会话
                        </button>
                      ) : null}
                    </div>
                  </>
                ) : null}
              </div>
            </>
          )}
        </article>
      </section>

      <section className="dashboard-section" style={{ display: "grid", gap: 16, gridTemplateColumns: "repeat(2, minmax(0, 1fr))" }}>
        <article className="settings-card">
          <div className="settings-card-header">
            <div>
              <strong>手工创建资源</strong>
              <p className="muted">适合先登记外部 CDN 或现有文件地址，再补做 Provider 同步。</p>
            </div>
          </div>

          <form className="meta-form" onSubmit={(event) => void handleCreateAsset(event)}>
            <label>
              账号
              <input
                value={createForm.account_id}
                onChange={(event) =>
                  setCreateForm((current) => ({ ...current, account_id: event.target.value }))
                }
              />
            </label>

            <label>
              WABA ID
              <input
                value={createForm.waba_id}
                onChange={(event) =>
                  setCreateForm((current) => ({ ...current, waba_id: event.target.value }))
                }
              />
            </label>

            <label>
              Phone-Number-ID
              <select
                value={createForm.phone_number_id}
                onChange={(event) =>
                  setCreateForm((current) => ({
                    ...current,
                    phone_number_id: event.target.value,
                  }))
                }
              >
                <option value="">不限定号码</option>
                {createPhoneOptions.map((phoneNumberId) => (
                  <option key={phoneNumberId} value={phoneNumberId}>
                    {phoneNumberId}
                  </option>
                ))}
              </select>
            </label>

            <label>
              资源名称
              <input
                value={createForm.name}
                onChange={(event) =>
                  setCreateForm((current) => ({ ...current, name: event.target.value }))
                }
              />
            </label>

            <label>
              资源类型
              <select
                value={createForm.asset_type}
                onChange={(event) =>
                  setCreateForm((current) => ({
                    ...current,
                    asset_type: event.target.value as MediaAssetType,
                  }))
                }
              >
                <option value="image">图片</option>
                <option value="audio">音频</option>
                <option value="video">视频</option>
                <option value="document">文档</option>
              </select>
            </label>

            <label>
              MIME 类型
              <input
                value={createForm.mime_type}
                onChange={(event) =>
                  setCreateForm((current) => ({ ...current, mime_type: event.target.value }))
                }
              />
            </label>

            <label>
              存储键（storage_key）
              <input
                value={createForm.storage_key}
                onChange={(event) =>
                  setCreateForm((current) => ({ ...current, storage_key: event.target.value }))
                }
              />
            </label>

            <label className="meta-form-span-2">
              存储地址（storage_url）
              <input
                value={createForm.storage_url}
                onChange={(event) =>
                  setCreateForm((current) => ({ ...current, storage_url: event.target.value }))
                }
              />
            </label>

            <label>
              Provider 引用（Phone-scoped）
              <input
                value={createForm.provider_media_id}
                onChange={(event) =>
                  setCreateForm((current) => ({
                    ...current,
                    provider_media_id: event.target.value,
                  }))
                }
              />
            </label>

            <label>
              标签
              <input
                value={createForm.tags_text}
                onChange={(event) =>
                  setCreateForm((current) => ({ ...current, tags_text: event.target.value }))
                }
                placeholder="多个标签用逗号分隔"
              />
            </label>

            <div className="meta-form-actions meta-form-span-2">
              <button className="seed-button" disabled={pendingAction !== null} type="submit">
                {pendingAction === "create-asset" ? "创建中..." : "创建资源"}
              </button>
            </div>
          </form>
        </article>

        <article className="settings-card">
          <div className="settings-card-header">
            <div>
              <strong>上传文件</strong>
              <p className="muted">上传后会直接生成资源记录，适合后续复用到模板头部或人工发送。</p>
            </div>
          </div>

          <form className="meta-form" onSubmit={(event) => void handleUploadAsset(event)}>
            <label>
              账号
              <input
                value={uploadForm.account_id}
                onChange={(event) =>
                  setUploadForm((current) => ({ ...current, account_id: event.target.value }))
                }
              />
            </label>

            <label>
              WABA ID
              <input
                value={uploadForm.waba_id}
                onChange={(event) =>
                  setUploadForm((current) => ({ ...current, waba_id: event.target.value }))
                }
              />
            </label>

            <label>
              Phone-Number-ID
              <select
                value={uploadForm.phone_number_id}
                onChange={(event) =>
                  setUploadForm((current) => ({
                    ...current,
                    phone_number_id: event.target.value,
                  }))
                }
              >
                <option value="">不限定号码</option>
                {uploadPhoneOptions.map((phoneNumberId) => (
                  <option key={phoneNumberId} value={phoneNumberId}>
                    {phoneNumberId}
                  </option>
                ))}
              </select>
            </label>

            <label>
              资源名称
              <input
                value={uploadForm.name}
                onChange={(event) =>
                  setUploadForm((current) => ({ ...current, name: event.target.value }))
                }
                placeholder="为空时沿用文件名"
              />
            </label>

            <label>
              来源
              <input
                value={uploadForm.source}
                onChange={(event) =>
                  setUploadForm((current) => ({ ...current, source: event.target.value }))
                }
              />
            </label>

            <label>
              标签
              <input
                value={uploadForm.tags_text}
                onChange={(event) =>
                  setUploadForm((current) => ({ ...current, tags_text: event.target.value }))
                }
              />
            </label>

            <label className="meta-form-span-2">
              文件
              <input
                onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)}
                type="file"
              />
            </label>

            <div className="meta-form-actions meta-form-span-2">
              <button className="seed-button" disabled={pendingAction !== null} type="submit">
                {pendingAction === "upload-asset" ? "上传中..." : "上传资源"}
              </button>
            </div>
          </form>
        </article>
      </section>
      <section className="dashboard-section">
        <article className="settings-card">
          <div className="settings-card-header">
            <div>
              <strong>同步记录与使用情况</strong>
              <p className="muted">
                这里保留 Provider 同步、模板引用和会话发送的最小闭环记录。按当前 Phone-Number-ID
                命中的 Provider 引用优先展示，Legacy Meta Media ID 仅作兼容字段查看。
              </p>
            </div>
          </div>

          {!selectedAssetDetail ? (
            <p className="muted">当前没有可展示的资源详情。</p>
          ) : (
            <>
              <div
                style={{
                  display: "grid",
                  gap: 12,
                  gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
                }}
              >
                <article className="queue-stat-card">
                  <strong>事件总数</strong>
                  <span>{selectedAssetDetail.usage.total_events}</span>
                  <p className="muted">资源事件流水</p>
                </article>
                <article className="queue-stat-card">
                  <strong>同步次数</strong>
                  <span>{selectedAssetDetail.usage.sync_count}</span>
                  <p className="muted">包含复用与重新上传</p>
                </article>
                <article className="queue-stat-card">
                  <strong>发送次数</strong>
                  <span>{selectedAssetDetail.usage.send_count}</span>
                  <p className="muted">会话直接发送次数</p>
                </article>
                <article className="queue-stat-card">
                  <strong>模板引用次数</strong>
                  <span>{selectedAssetDetail.usage.template_send_count}</span>
                  <p className="muted">模板头部媒体引用</p>
                </article>
              </div>

              <div className="template-log-list" style={{ marginTop: 16 }}>
                {selectedAssetDetail.provider_syncs.map((sync) => (
                  <article className="template-log-row" key={sync.id}>
                    <div className="template-card-header">
                      <strong>{sync.provider_name}</strong>
                      <span className={getSyncBadgeClass(sync.sync_status)}>
                        {formatSyncStatus(sync.sync_status)}
                      </span>
                    </div>
                    <div className="template-detail-grid">
                      <span>{`WABA ID：${formatOptionalText(sync.waba_id)}`}</span>
                      <span>{`Phone-Number-ID：${formatOptionalText(sync.phone_number_id)}`}</span>
                      <span>{`Provider 引用：${formatOptionalText(getProviderReferenceValue(sync))}`}</span>
                      <span>{`Legacy Meta Media ID（兼容字段）：${formatOptionalText(sync.meta_media_id)}`}</span>
                      <span>{`同步时间：${formatTimestamp(sync.last_synced_at)}`}</span>
                      <span>{`错误码：${formatOptionalText(sync.last_error_code)}`}</span>
                    </div>
                    {sync.last_error_message ? (
                      <p className="status-error">{sync.last_error_message}</p>
                    ) : null}
                  </article>
                ))}
                {selectedAssetDetail.provider_syncs.length === 0 ? (
                  <p className="muted">当前资源还没有 Provider 同步记录。</p>
                ) : null}
              </div>

              <div className="template-log-list" style={{ marginTop: 16 }}>
                {selectedAssetDetail.events.slice(0, 20).map((event) => (
                  <article className="template-log-row" key={event.id}>
                    <div className="template-card-header">
                      <strong>{event.event_type}</strong>
                      <span className="badge badge-neutral">{formatTimestamp(event.created_at)}</span>
                    </div>
                    <div className="template-detail-grid">
                      <span>{`账号：${formatAccountLabel(event.account_id, accountMap)}`}</span>
                      <span>{`WABA ID：${formatOptionalText(event.waba_id)}`}</span>
                      <span>{`Phone-Number-ID：${formatOptionalText(event.phone_number_id)}`}</span>
                      <span>{`Provider 引用：${formatOptionalText(getProviderReferenceValue(event))}`}</span>
                      <span>{`Legacy Meta Media ID（兼容字段）：${formatOptionalText(event.meta_media_id)}`}</span>
                      <span>{`操作人：${event.created_by ?? "系统"}`}</span>
                    </div>
                  </article>
                ))}
                {selectedAssetDetail.events.length === 0 ? (
                  <p className="muted">当前资源还没有事件记录。</p>
                ) : null}
              </div>
            </>
          )}
        </article>
      </section>
    </Panel>
  );
}
