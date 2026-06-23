import type { JSX } from "react";
import { Space, Tag, Tooltip } from "antd";

import type { ConsoleDataSourceTone } from "../types/console";

export type AdminDataSourceLegendItem = {
  text: string;
  tone: ConsoleDataSourceTone;
};

type AdminDataSourceLegendProps = {
  items: AdminDataSourceLegendItem[];
};

function getToneColor(tone: ConsoleDataSourceTone): string {
  if (tone === "api") return "blue";
  if (tone === "hybrid") return "cyan";
  if (tone === "mock") return "gold";
  return "default";
}

function getToneLabel(tone: ConsoleDataSourceTone): string {
  if (tone === "api") return "API";
  if (tone === "hybrid") return "混合";
  if (tone === "mock") return "模拟";
  return "占位";
}

export function AdminDataSourceLegend({
  items,
}: AdminDataSourceLegendProps): JSX.Element | null {
  const tones = items.reduce<Array<{ tone: ConsoleDataSourceTone; texts: string[] }>>((list, item) => {
    const existing = list.find((entry) => entry.tone === item.tone);
    if (existing) {
      if (item.text.trim() && !existing.texts.includes(item.text.trim())) {
        existing.texts.push(item.text.trim());
      }
    } else {
      list.push({
        tone: item.tone,
        texts: item.text.trim() ? [item.text.trim()] : [],
      });
    }
    return list;
  }, []);

  if (!tones.length) {
    return null;
  }

  return (
    <Space size={[8, 8]} wrap>
      {tones.map((entry) => {
        const tag = (
          <Tag color={getToneColor(entry.tone)} key={entry.tone}>
            {getToneLabel(entry.tone)}
          </Tag>
        );

        if (!entry.texts.length) {
          return tag;
        }

        return (
          <Tooltip key={entry.tone} title={entry.texts.join(" / ")}>
            {tag}
          </Tooltip>
        );
      })}
    </Space>
  );
}
