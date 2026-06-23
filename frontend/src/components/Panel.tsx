import type { ReactNode } from "react";

import { ProCard } from "@ant-design/pro-card";

type PanelProps = {
  title: string;
  children: ReactNode;
};

export function Panel({ title, children }: PanelProps) {
  return (
    <ProCard
      bordered
      className="admin-panel"
      colSpan="100%"
      headerBordered
      title={title}
    >
      {children}
    </ProCard>
  );
}
