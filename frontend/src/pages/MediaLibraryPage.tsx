import { useCallback, type JSX } from "react";
import { Button, Card, Col, Row, Space, Tag, Typography } from "antd";

import { EmptyGuide, PageShell } from "../components/PageShell";
import { usePageData } from "../hooks/usePageData";
import { listMediaAssets, type MediaAssetView } from "../services/api";

const TYPE_COLORS: Record<string, string> = {
  audio: "#722ed1",
  document: "#fa8c16",
  image: "#1677ff",
  video: "#eb2f96",
};

const TYPE_LABELS: Record<string, string> = {
  audio: "音频",
  document: "文档",
  image: "图片",
  video: "视频",
};

function isImage(mimeType: string): boolean {
  return mimeType.startsWith("image/");
}

export function MediaLibraryPage(): JSX.Element {
  const fetchData = useCallback(async () => {
    const assets = await listMediaAssets();
    return { assets };
  }, []);

  const { data, error, loading, reload } = usePageData({ fetcher: fetchData });
  const assets = data?.assets ?? [];
  const imageAssets = assets.filter((item) => isImage(item.mime_type));
  const otherAssets = assets.filter((item) => !isImage(item.mime_type));

  const stats = (
    <Space size="middle" style={{ fontSize: 13 }}>
      <span>
        总数 <Typography.Text strong>{assets.length}</Typography.Text>
      </span>
      <span>
        图片 <Typography.Text strong style={{ color: "#1677ff" }}>{imageAssets.length}</Typography.Text>
      </span>
      <span>
        其他 <Typography.Text strong style={{ color: "#fa8c16" }}>{otherAssets.length}</Typography.Text>
      </span>
    </Space>
  );

  const actions = (
    <Button loading={loading} onClick={() => void reload()} size="small">
      刷新
    </Button>
  );

  const renderAssetCard = (asset: MediaAssetView): JSX.Element => (
    <Col key={asset.asset_id} lg={4} md={6} sm={8} xs={12}>
      <Card
        cover={
          isImage(asset.mime_type) && asset.storage_url ? (
            <div
              style={{
                alignItems: "center",
                background: "#f5f5f5",
                display: "flex",
                height: 120,
                justifyContent: "center",
                overflow: "hidden",
              }}
            >
              <img
                alt={asset.name}
                src={asset.storage_url}
                style={{ maxHeight: "100%", maxWidth: "100%", objectFit: "contain" }}
              />
            </div>
          ) : (
            <div
              style={{
                alignItems: "center",
                background: "#fafafa",
                display: "flex",
                fontSize: 24,
                height: 80,
                justifyContent: "center",
              }}
            >
              {asset.asset_type === "video" ? "🎬" : asset.asset_type === "audio" ? "🎧" : "📄"}
            </div>
          )
        }
        hoverable
        size="small"
      >
        <Typography.Text ellipsis style={{ display: "block", fontSize: 12 }}>
          {asset.name}
        </Typography.Text>
        <div style={{ alignItems: "center", display: "flex", gap: 4, marginTop: 4 }}>
          <Tag color={TYPE_COLORS[asset.asset_type] ?? "default"} style={{ fontSize: 9, margin: 0 }}>
            {TYPE_LABELS[asset.asset_type] ?? asset.asset_type}
          </Tag>
          <Tag color={asset.is_active ? "success" : "default"} style={{ fontSize: 9, margin: 0 }}>
            {asset.is_active ? "启用" : "停用"}
          </Tag>
        </div>
        {asset.file_size != null ? (
          <Typography.Text style={{ color: "#999", display: "block", fontSize: 10, marginTop: 2 }}>
            {(asset.file_size / 1024).toFixed(1)} KB
          </Typography.Text>
        ) : null}
      </Card>
    </Col>
  );

  if (!assets.length && !loading) {
    return (
      <PageShell actions={actions} stats={stats} subtitle="管理已上传的媒体文件" title="媒体库">
        <EmptyGuide description="当前还没有媒体文件。" icon="🖼️" title="暂无媒体" />
      </PageShell>
    );
  }

  return (
    <PageShell actions={actions} stats={stats} subtitle="管理已上传的媒体文件" title="媒体库">
      {error ? (
        <Typography.Text style={{ display: "block", marginBottom: 12 }} type="danger">
          {error}
        </Typography.Text>
      ) : null}
      <div style={{ height: "100%", overflowY: "auto" }}>
        {imageAssets.length ? (
          <div style={{ marginBottom: 16 }}>
            <Typography.Title level={5} style={{ margin: "0 0 8px" }}>
              图片 ({imageAssets.length})
            </Typography.Title>
            <Row gutter={[8, 8]}>{imageAssets.map(renderAssetCard)}</Row>
          </div>
        ) : null}
        {otherAssets.length ? (
          <div>
            <Typography.Title level={5} style={{ margin: "0 0 8px" }}>
              其他文件 ({otherAssets.length})
            </Typography.Title>
            <Row gutter={[8, 8]}>{otherAssets.map(renderAssetCard)}</Row>
          </div>
        ) : null}
      </div>
    </PageShell>
  );
}
