import { useCallback, useRef, useState, type JSX } from "react";

import { DownloadOutlined } from "@ant-design/icons";
import { Button, Progress, message } from "antd";

export interface ExportColumn {
  key: string;
  label: string;
}

interface DataExporterProps {
  columns: ExportColumn[];
  fetchData: (page: number) => Promise<{ data: Record<string, unknown>[]; total: number }>;
  filename: string;
  maxRows?: number;
}

type ExportState =
  | { status: "idle" }
  | { status: "exporting"; progress: number }
  | { status: "polling"; exportId: string; progress: number }
  | { status: "done" }
  | { status: "error"; error: string };

/**
 * Escape a single CSV field value.
 * Wraps in double-quotes when the value contains commas, double-quotes, or
 * newlines, and doubles any embedded double-quotes per RFC 4180.
 */
function escapeCSV(value: unknown): string {
  if (value === null || value === undefined) return "";
  const str = String(value);
  if (str.includes(",") || str.includes('"') || str.includes("\n") || str.includes("\r")) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

/**
 * Convert a data array to a CSV string.
 * Prepends a UTF-8 BOM so Chinese (and other) characters are rendered
 * correctly in Excel / WPS.
 */
function generateCSV(
  columns: ExportColumn[],
  data: Record<string, unknown>[],
): string {
  const bom = "\uFEFF";
  const header = columns.map((col) => escapeCSV(col.label)).join(",");
  const rows = data.map((row) =>
    columns.map((col) => escapeCSV(row[col.key])).join(","),
  );
  return bom + header + "\n" + rows.join("\n");
}

/**
 * Create a Blob download link in the browser and click it programmatically.
 */
function downloadBlob(content: string, filename: string): void {
  const blob = new Blob([content], {
    type: "text/csv;charset=utf-8;header=present",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename.endsWith(".csv") ? filename : `${filename}.csv`;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

/**
 * Poll the backend export status endpoint every 2 seconds until the export
 * completes or fails.
 */
async function pollExportStatus(
  exportId: string,
  signal: AbortSignal,
  onProgress: (pct: number) => void,
): Promise<string> {
  while (!signal.aborted) {
    await new Promise((resolve) => setTimeout(resolve, 2000));
    if (signal.aborted) break;

    const resp = await fetch(`/api/exports/${exportId}/status`, { signal });
    if (!resp.ok) {
      throw new Error("导出状态查询失败");
    }

    const body = (await resp.json()) as {
      status: string;
      progress: number;
      download_url?: string;
    };

    onProgress(body.progress);

    if (body.status === "completed" && body.download_url) {
      return body.download_url;
    }
    if (body.status === "failed") {
      throw new Error("导出失败");
    }
  }
  throw new Error("导出已取消");
}

function isAbortError(err: unknown): boolean {
  return (
    err instanceof DOMException &&
    (err.name === "AbortError" || err.name === "TimeoutError")
  );
}

export function DataExporter(props: DataExporterProps): JSX.Element {
  const { columns, fetchData, filename, maxRows = 100 } = props;
  const [state, setState] = useState<ExportState>({ status: "idle" });
  const abortRef = useRef<AbortController | null>(null);

  const isBusy = state.status === "exporting" || state.status === "polling";
  const progressValue = isBusy ? state.progress : 0;

  const handleExport = useCallback(async () => {
    if (isBusy) return;

    const controller = new AbortController();
    abortRef.current = controller;

    setState({ status: "exporting", progress: 0 });

    try {
      const first = await fetchData(1);
      const total = first.total;

      if (total <= maxRows) {
        /* ---------- client-side CSV export ---------- */
        const allData: Record<string, unknown>[] = [...first.data];
        const pageSize = first.data.length;

        if (pageSize > 0 && total > pageSize) {
          const totalPages = Math.ceil(total / pageSize);
          for (let p = 2; p <= totalPages; p++) {
            if (controller.signal.aborted) {
              throw new DOMException("Aborted", "AbortError");
            }
            const page = await fetchData(p);
            allData.push(...page.data);
            setState({
              status: "exporting" as const,
              progress: Math.round(((p - 1) / (totalPages - 1)) * 100),
            });
          }
        }

        const csv = generateCSV(columns, allData);
        downloadBlob(csv, filename);
        setState({ status: "done" });
        void message.success("导出完成");
      } else {
        /* ---------- backend export ---------- */
        const resp = await fetch("/api/exports", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ columns, max_rows: maxRows }),
          signal: controller.signal,
        });

        if (!resp.ok) {
          throw new Error("创建导出任务失败");
        }

        const { export_id: exportId } = (await resp.json()) as {
          export_id: string;
        };

        setState({
          status: "polling",
          exportId,
          progress: 0,
        });

        const downloadUrl = await pollExportStatus(
          exportId,
          controller.signal,
          (pct) => {
            setState((prev) =>
              prev.status === "polling"
                ? { ...prev, progress: pct }
                : prev,
            );
          },
        );

        /* trigger download from server-provided URL */
        const anchor = document.createElement("a");
        anchor.href = downloadUrl;
        anchor.download = filename.endsWith(".csv")
          ? filename
          : `${filename}.csv`;
        anchor.rel = "noopener noreferrer";
        document.body.appendChild(anchor);
        anchor.click();
        document.body.removeChild(anchor);

        setState({ status: "done" });
        void message.success("导出完成");
      }
    } catch (err: unknown) {
      if (isAbortError(err)) {
        setState({ status: "idle" });
        return;
      }
      const errorMessage =
        err instanceof Error ? err.message : "导出失败";
      setState({ status: "error", error: errorMessage });
      void message.error(errorMessage);
    }
  }, [columns, fetchData, filename, maxRows, isBusy]);

  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
      <Button
        icon={<DownloadOutlined />}
        loading={isBusy}
        onClick={() => void handleExport()}
        type="default"
      >
        导出CSV
      </Button>
      {isBusy ? (
        <Progress percent={progressValue} size="small" style={{ width: 120 }} />
      ) : null}
    </span>
  );
}
