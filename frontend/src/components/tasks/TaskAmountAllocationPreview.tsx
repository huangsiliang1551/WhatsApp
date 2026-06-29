import { Empty, Space, Typography } from "antd";

type TaskAmountAllocationPreviewProps = {
  amounts: string[];
  total: string | null;
  emptyText?: string;
};

export function TaskAmountAllocationPreview({
  amounts,
  total,
  emptyText = "Run amount preview first to inspect the allocation result.",
}: TaskAmountAllocationPreviewProps) {
  if (amounts.length === 0) {
    return <Empty description={emptyText} image={Empty.PRESENTED_IMAGE_SIMPLE} />;
  }

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={4}>
      {amounts.map((amount, index) => (
        <Typography.Text key={`${index + 1}-${amount}`}>
          {index + 1}/{amounts.length}: {amount}
        </Typography.Text>
      ))}
      <Typography.Text strong>Total: {total ?? "-"}</Typography.Text>
    </Space>
  );
}
