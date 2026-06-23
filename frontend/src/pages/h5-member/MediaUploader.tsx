import { type JSX, useState, useRef, useCallback } from "react";
import { InboxOutlined, CloseOutlined, LoadingOutlined, CheckCircleOutlined, CloseCircleOutlined } from "@ant-design/icons";
import { t } from "./i18n";

// ─── Types ─────────────────────────────────────────────────────

export interface UploadedFile {
  id: string;
  file: File;
  url: string;
  name: string;
  size: number;
  compressedSize?: number;
  progress: number;
  status: "pending" | "uploading" | "done" | "error";
}

export interface MediaUploaderProps {
  accept?: string;
  maxSizeMB?: number;
  multiple?: boolean;
  onUpload: (files: UploadedFile[]) => void;
  onError?: (error: string) => void;
  preview?: boolean;
  compress?: boolean;
}

// ─── Image compression utility ─────────────────────────────────

async function compressImage(file: File, maxWidth = 1200, quality = 0.8): Promise<Blob> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      URL.revokeObjectURL(url);
      const canvas = document.createElement("canvas");
      let { width, height } = img;
      if (width > maxWidth) {
        height = (height * maxWidth) / width;
        width = maxWidth;
      }
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext("2d");
      if (!ctx) { reject(new Error("Canvas not supported")); return; }
      ctx.drawImage(img, 0, 0, width, height);
      canvas.toBlob((blob) => {
        if (blob) resolve(blob);
        else reject(new Error("Compression failed"));
      }, "image/jpeg", quality);
    };
    img.onerror = () => reject(new Error("Image load failed"));
    img.src = url;
  });
}

let fileIdCounter = 0;
function nextFileId(): string {
  fileIdCounter += 1;
  return `media-${Date.now()}-${fileIdCounter}`;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ─── Component ─────────────────────────────────────────────────

export function MediaUploader({
  accept = "image/*",
  maxSizeMB = 5,
  multiple = false,
  onUpload,
  onError,
  preview = true,
  compress = true,
}: MediaUploaderProps): JSX.Element {
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const [isCompressing, setIsCompressing] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const maxSizeBytes = maxSizeMB * 1024 * 1024;

  const processFiles = useCallback(async (rawFiles: FileList | File[]) => {
    const fileArray = Array.from(rawFiles).filter((f) => {
      // File type validation
      if (accept !== "*/*") {
        const acceptTypes = accept.split(",").map((a) => a.trim());
        const matchesType = acceptTypes.some((type) => {
          if (type.endsWith("/*")) {
            const category = type.replace("/*", "");
            return f.type.startsWith(category + "/");
          }
          return f.type === type;
        });
        if (!matchesType) {
          onError?.(t("media.typeError", { name: f.name, accept }));
          return false;
        }
      }
      // File size validation
      if (f.size > maxSizeBytes) {
        onError?.(t("media.sizeError", { name: f.name, maxSize: String(maxSizeMB) }));
        return false;
      }
      return true;
    });

    if (fileArray.length === 0) return;

    setIsCompressing(true);
    const processed: UploadedFile[] = [];

    for (const file of fileArray) {
      const id = nextFileId();
      const shouldCompress = compress && file.size > 1024 * 1024 && file.type.startsWith("image/");

      if (shouldCompress) {
        try {
          const compressedBlob = await compressImage(file);
          const compressedFile = new File([compressedBlob], file.name.replace(/\.[^.]+$/, ".jpg"), { type: "image/jpeg" });
          const url = URL.createObjectURL(compressedFile);
          processed.push({
            id,
            file: compressedFile,
            url,
            name: compressedFile.name,
            size: file.size,
            compressedSize: compressedFile.size,
            progress: 0,
            status: "pending",
          });
        } catch {
          // Fall back to original
          const url = URL.createObjectURL(file);
          processed.push({
            id,
            file,
            url,
            name: file.name,
            size: file.size,
            progress: 0,
            status: "pending",
          });
        }
      } else {
        const url = URL.createObjectURL(file);
        processed.push({
          id,
          file,
          url,
          name: file.name,
          size: file.size,
          progress: 0,
          status: "pending",
        });
      }
    }

    setIsCompressing(false);

    setFiles((prev) => {
      const updated = multiple ? [...prev, ...processed] : processed;
      return updated;
    });

    // Reset input
    if (inputRef.current) {
      inputRef.current.value = "";
    }
  }, [accept, maxSizeBytes, maxSizeMB, multiple, compress, onError]);

  const handleFileSelect = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const rawFiles = event.target.files;
    if (!rawFiles || rawFiles.length === 0) return;
    void processFiles(rawFiles);
  }, [processFiles]);

  const handleDrop = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragOver(false);
    const droppedFiles = event.dataTransfer.files;
    if (droppedFiles.length === 0) return;
    void processFiles(droppedFiles);
  }, [processFiles]);

  const handleDragOver = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleRemove = useCallback((id: string) => {
    setFiles((prev) => {
      const removed = prev.find((f) => f.id === id);
      if (removed) {
        URL.revokeObjectURL(removed.url);
      }
      return prev.filter((f) => f.id !== id);
    });
  }, []);

  const handleCancelUpload = useCallback((id: string) => {
    setFiles((prev) => prev.filter((f) => f.id !== id));
  }, []);

  const handleUpload = useCallback(() => {
    setFiles((prev) => {
      const updated = prev.map((f) => {
        if (f.status === "pending") {
          return { ...f, status: "uploading" as const, progress: 0 };
        }
        return f;
      });
      return updated;
    });

    // Simulate progress and then mark as done
    setTimeout(() => {
      setFiles((prev) => {
        const updated = prev.map((f) => {
          if (f.status === "uploading") {
            return { ...f, progress: 50 };
          }
          return f;
        });
        return updated;
      });
    }, 200);

    setTimeout(() => {
      setFiles((prev) => {
        const uploaded = prev.filter((f) => f.status === "uploading").map((f) => ({
          ...f,
          progress: 100,
          status: "done" as const,
        }));
        const rest = prev.filter((f) => f.status !== "uploading");
        const result = [...rest, ...uploaded];
        onUpload(result.filter((f) => f.status === "done"));
        return result;
      });
    }, 600);
  }, [onUpload]);

  const hasPendingFiles = files.some((f) => f.status === "pending");
  const hasUploadingFiles = files.some((f) => f.status === "uploading");

  return (
    <div className="h5-media-uploader">
      {/* Drop zone */}
      <div
        className={`h5-media-dropzone ${isDragOver ? "h5-media-dropzone-active" : ""}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") inputRef.current?.click(); }}
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          multiple={multiple}
          style={{ display: "none" }}
          onChange={handleFileSelect}
        />
        <InboxOutlined className="h5-media-dropzone-icon" />
        <p className="h5-media-dropzone-text">{t("media.dragDrop")}</p>
        <p className="h5-media-dropzone-hint">{t("media.selectFile", { accept: accept === "image/*" ? "JPG/PNG" : accept })}</p>
        <p className="h5-media-dropzone-hint">{t("media.sizeLimit", { maxSize: String(maxSizeMB) })}</p>
      </div>

      {/* Compression progress */}
      {isCompressing ? (
        <div className="h5-media-compression-info">
          <LoadingOutlined /> {t("media.compressing")}
        </div>
      ) : null}

      {/* Upload action buttons */}
      {files.length > 0 ? (
        <div className="h5-media-actions">
          <button
            className="h5-media-upload-btn"
            disabled={!hasPendingFiles || hasUploadingFiles}
            onClick={handleUpload}
            type="button"
          >
            {hasUploadingFiles ? t("media.uploading") : t("media.upload", { count: files.filter((f) => f.status === "pending").length })}
          </button>
        </div>
      ) : null}

      {/* Preview grid */}
      {preview && files.length > 0 ? (
        <div className="h5-media-preview-grid">
          {files.map((file) => (
            <div className="h5-media-preview-item" key={file.id}>
              {/* Thumbnail */}
              {file.file.type.startsWith("image/") ? (
                <img
                  alt={file.name}
                  className="h5-media-preview-thumb"
                  src={file.url}
                />
              ) : (
                <div className="h5-media-preview-thumb h5-media-preview-file-icon">
                  <InboxOutlined />
                </div>
              )}

              {/* File name */}
              <p className="h5-media-preview-name" title={file.name}>{file.name}</p>

              {/* Size info */}
              <p className="h5-media-preview-size">
                {formatFileSize(file.size)}
                {file.compressedSize != null ? (
                  <span className="h5-media-compression-info">
                    {" → "}{formatFileSize(file.compressedSize)}
                    {" "}{t("media.compressInfo", { ratio: formatFileSize(file.size - file.compressedSize) })}
                  </span>
                ) : null}
              </p>

              {/* Progress bar */}
              {(file.status === "uploading" || file.status === "done") ? (
                <div className="h5-media-progress-bar">
                  <div
                    className="h5-media-progress-fill"
                    style={{ width: `${file.progress}%` }}
                  />
                </div>
              ) : null}

              {/* Status icon */}
              <div className="h5-media-preview-status">
                {file.status === "uploading" ? (
                  <LoadingOutlined className="h5-media-status-uploading" />
                ) : file.status === "done" ? (
                  <CheckCircleOutlined className="h5-media-status-done" />
                ) : file.status === "error" ? (
                  <CloseCircleOutlined className="h5-media-status-error" />
                ) : null}
              </div>

              {/* Remove button (only for pending files) */}
              {file.status === "pending" ? (
                <button
                  className="h5-media-remove-btn"
                  onClick={(e) => { e.stopPropagation(); handleRemove(file.id); }}
                  title={t("media.remove")}
                  type="button"
                >
                  <CloseOutlined />
                </button>
              ) : null}

              {/* Cancel upload button */}
              {file.status === "uploading" ? (
                <button
                  className="h5-media-cancel-btn"
                  onClick={(e) => { e.stopPropagation(); handleCancelUpload(file.id); }}
                  title={t("media.cancel")}
                  type="button"
                >
                  <CloseOutlined />
                </button>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
