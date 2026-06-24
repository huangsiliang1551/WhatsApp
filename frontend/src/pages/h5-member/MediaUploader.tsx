import { CheckCircleOutlined, CloseCircleOutlined, CloseOutlined, InboxOutlined, LoadingOutlined } from "@ant-design/icons";
import { type JSX, useCallback, useRef, useState } from "react";

import { t } from "./i18n";

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
      if (!ctx) {
        reject(new Error("Canvas not supported"));
        return;
      }

      ctx.drawImage(img, 0, 0, width, height);
      canvas.toBlob((blob) => {
        if (blob) {
          resolve(blob);
        } else {
          reject(new Error("Compression failed"));
        }
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
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

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

  const processFiles = useCallback(
    async (rawFiles: FileList | File[]) => {
      const fileArray = Array.from(rawFiles).filter((file) => {
        if (accept !== "*/*") {
          const acceptTypes = accept.split(",").map((item) => item.trim());
          const matchesType = acceptTypes.some((type) => {
            if (type.endsWith("/*")) {
              const category = type.replace("/*", "");
              return file.type.startsWith(`${category}/`);
            }
            return file.type === type;
          });

          if (!matchesType) {
            onError?.(t("media.typeError", { name: file.name, accept }));
            return false;
          }
        }

        if (file.size > maxSizeBytes) {
          onError?.(t("media.sizeError", { name: file.name, maxSize: String(maxSizeMB) }));
          return false;
        }

        return true;
      });

      if (!fileArray.length) {
        return;
      }

      setIsCompressing(true);
      const processed: UploadedFile[] = [];

      for (const file of fileArray) {
        const id = nextFileId();
        const shouldCompress = compress && file.size > 1024 * 1024 && file.type.startsWith("image/");

        if (shouldCompress) {
          try {
            const compressedBlob = await compressImage(file);
            const compressedFile = new File([compressedBlob], file.name.replace(/\.[^.]+$/, ".jpg"), {
              type: "image/jpeg",
            });
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

      setFiles((prev) => (multiple ? [...prev, ...processed] : processed));

      if (inputRef.current) {
        inputRef.current.value = "";
      }
    },
    [accept, compress, maxSizeBytes, maxSizeMB, multiple, onError],
  );

  const handleFileSelect = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const rawFiles = event.target.files;
      if (!rawFiles || rawFiles.length === 0) {
        return;
      }
      void processFiles(rawFiles);
    },
    [processFiles],
  );

  const handleDrop = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      setIsDragOver(false);
      const droppedFiles = event.dataTransfer.files;
      if (!droppedFiles.length) {
        return;
      }
      void processFiles(droppedFiles);
    },
    [processFiles],
  );

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
      const removed = prev.find((file) => file.id === id);
      if (removed) {
        URL.revokeObjectURL(removed.url);
      }
      return prev.filter((file) => file.id !== id);
    });
  }, []);

  const handleCancelUpload = useCallback((id: string) => {
    setFiles((prev) => prev.filter((file) => file.id !== id));
  }, []);

  const handleUpload = useCallback(() => {
    setFiles((prev) =>
      prev.map((file) => (file.status === "pending" ? { ...file, status: "uploading" as const, progress: 0 } : file)),
    );

    setTimeout(() => {
      setFiles((prev) =>
        prev.map((file) => (file.status === "uploading" ? { ...file, progress: 50 } : file)),
      );
    }, 200);

    setTimeout(() => {
      setFiles((prev) => {
        const uploaded = prev
          .filter((file) => file.status === "uploading")
          .map((file) => ({ ...file, progress: 100, status: "done" as const }));
        const rest = prev.filter((file) => file.status !== "uploading");
        const result = [...rest, ...uploaded];
        onUpload(result.filter((file) => file.status === "done"));
        return result;
      });
    }, 600);
  }, [onUpload]);

  const hasPendingFiles = files.some((file) => file.status === "pending");
  const hasUploadingFiles = files.some((file) => file.status === "uploading");

  return (
    <div className="h5-media-uploader">
      <div
        className={`h5-media-dropzone ${isDragOver ? "h5-media-dropzone-active" : ""}`}
        onClick={() => inputRef.current?.click()}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            inputRef.current?.click();
          }
        }}
        role="button"
        tabIndex={0}
      >
        <input
          ref={inputRef}
          accept={accept}
          className="h5-media-input"
          multiple={multiple}
          onChange={handleFileSelect}
          type="file"
        />
        <InboxOutlined className="h5-media-dropzone-icon" />
        <p className="h5-media-dropzone-text">{t("media.dragDrop")}</p>
        <p className="h5-media-dropzone-hint">{t("media.selectFile", { accept: accept === "image/*" ? "JPG/PNG" : accept })}</p>
        <p className="h5-media-dropzone-hint">{t("media.sizeLimit", { maxSize: String(maxSizeMB) })}</p>
      </div>

      {isCompressing ? (
        <div className="h5-media-compression-info">
          <LoadingOutlined /> {t("media.compressing")}
        </div>
      ) : null}

      {files.length > 0 ? (
        <div className="h5-media-actions">
          <button
            className="h5-media-upload-btn"
            disabled={!hasPendingFiles || hasUploadingFiles}
            onClick={handleUpload}
            type="button"
          >
            {hasUploadingFiles ? t("media.uploading") : t("media.upload", { count: files.filter((file) => file.status === "pending").length })}
          </button>
        </div>
      ) : null}

      {preview && files.length > 0 ? (
        <div className="h5-media-preview-grid">
          {files.map((file) => (
            <div className="h5-media-preview-item" key={file.id}>
              {file.file.type.startsWith("image/") ? (
                <img alt={file.name} className="h5-media-preview-thumb" src={file.url} />
              ) : (
                <div className="h5-media-preview-thumb h5-media-preview-file-icon">
                  <InboxOutlined />
                </div>
              )}

              <p className="h5-media-preview-name" title={file.name}>
                {file.name}
              </p>

              <p className="h5-media-preview-size">
                {formatFileSize(file.size)}
                {file.compressedSize != null ? (
                  <span className="h5-media-compression-info">
                    <span aria-hidden="true" className="h5-media-compression-arrow">-&gt;</span>
                    {formatFileSize(file.compressedSize)}
                    {" "}
                    {t("media.compressInfo", { ratio: formatFileSize(file.size - file.compressedSize) })}
                  </span>
                ) : null}
              </p>

              {file.status === "uploading" || file.status === "done" ? (
                <div className="h5-media-progress-bar">
                  <div className="h5-media-progress-fill" style={{ width: `${file.progress}%` }} />
                </div>
              ) : null}

              <div className="h5-media-preview-status">
                {file.status === "uploading" ? <LoadingOutlined className="h5-media-status-uploading" /> : null}
                {file.status === "done" ? <CheckCircleOutlined className="h5-media-status-done" /> : null}
                {file.status === "error" ? <CloseCircleOutlined className="h5-media-status-error" /> : null}
              </div>

              {file.status === "pending" ? (
                <button
                  className="h5-media-remove-btn"
                  onClick={(event) => {
                    event.stopPropagation();
                    handleRemove(file.id);
                  }}
                  title={t("media.remove")}
                  type="button"
                >
                  <CloseOutlined />
                </button>
              ) : null}

              {file.status === "uploading" ? (
                <button
                  className="h5-media-cancel-btn"
                  onClick={(event) => {
                    event.stopPropagation();
                    handleCancelUpload(file.id);
                  }}
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
