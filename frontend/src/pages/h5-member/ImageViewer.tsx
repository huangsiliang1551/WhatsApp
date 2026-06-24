import { CloseOutlined } from "@ant-design/icons";
import { useCallback, useEffect, useRef, useState, type JSX } from "react";

import { t } from "./i18n";

interface ImageViewerProps {
  images: string[];
  initialIndex?: number;
  onClose: () => void;
}

const SWIPE_THRESHOLD = 50;
const LONG_PRESS_MS = 600;
const MAX_ZOOM = 4;
const MIN_ZOOM = 1;

export function ImageViewer({
  images,
  initialIndex = 0,
  onClose,
}: ImageViewerProps): JSX.Element {
  const [currentIndex, setCurrentIndex] = useState(initialIndex);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [showTooltip, setShowTooltip] = useState(false);

  const imgRef = useRef<HTMLImageElement>(null);
  const overlayRef = useRef<HTMLDivElement>(null);
  const longPressTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const touchStartRef = useRef<{ x: number; y: number; time: number } | null>(null);
  const pinchRef = useRef<{ dist: number; zoom: number } | null>(null);
  const panStartRef = useRef<{ x: number; y: number } | null>(null);

  const total = images.length;
  const hasMultiple = total > 1;

  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      switch (event.key) {
        case "Escape":
          onClose();
          break;
        case "ArrowLeft":
          setCurrentIndex((prev) => (prev > 0 ? prev - 1 : prev));
          break;
        case "ArrowRight":
          setCurrentIndex((prev) => (prev < total - 1 ? prev + 1 : prev));
          break;
      }
    },
    [onClose, total],
  );

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  useEffect(() => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
    setShowTooltip(false);
  }, [currentIndex]);

  const startLongPress = useCallback(() => {
    longPressTimer.current = setTimeout(() => {
      setShowTooltip(true);
      setTimeout(() => setShowTooltip(false), 2500);
    }, LONG_PRESS_MS);
  }, []);

  const clearLongPress = useCallback(() => {
    if (longPressTimer.current) {
      clearTimeout(longPressTimer.current);
      longPressTimer.current = null;
    }
  }, []);

  const handleTouchStart = useCallback(
    (event: React.TouchEvent) => {
      if (event.touches.length === 1) {
        const touch = event.touches[0];
        touchStartRef.current = { x: touch.clientX, y: touch.clientY, time: Date.now() };
        panStartRef.current = { x: pan.x, y: pan.y };
        startLongPress();
      } else if (event.touches.length === 2) {
        clearLongPress();
        const dx = event.touches[0].clientX - event.touches[1].clientX;
        const dy = event.touches[0].clientY - event.touches[1].clientY;
        pinchRef.current = { dist: Math.hypot(dx, dy), zoom };
        touchStartRef.current = null;
      }
    },
    [clearLongPress, pan.x, pan.y, startLongPress, zoom],
  );

  const handleTouchMove = useCallback(
    (event: React.TouchEvent) => {
      if (event.touches.length === 2 && pinchRef.current) {
        const dx = event.touches[0].clientX - event.touches[1].clientX;
        const dy = event.touches[0].clientY - event.touches[1].clientY;
        const dist = Math.hypot(dx, dy);
        const nextZoom = Math.max(
          MIN_ZOOM,
          Math.min(MAX_ZOOM, (dist / pinchRef.current.dist) * pinchRef.current.zoom),
        );
        setZoom(nextZoom);
        if (nextZoom <= 1) {
          setPan({ x: 0, y: 0 });
        }
      } else if (event.touches.length === 1 && touchStartRef.current && zoom > 1) {
        const touch = event.touches[0];
        const deltaX = touch.clientX - touchStartRef.current.x;
        const deltaY = touch.clientY - touchStartRef.current.y;
        setPan({
          x: (panStartRef.current?.x ?? 0) + deltaX,
          y: (panStartRef.current?.y ?? 0) + deltaY,
        });
        clearLongPress();
      } else if (event.touches.length === 1) {
        clearLongPress();
      }
    },
    [clearLongPress, zoom],
  );

  const handleTouchEnd = useCallback(
    (event: React.TouchEvent) => {
      clearLongPress();
      pinchRef.current = null;

      const start = touchStartRef.current;
      if (!start) {
        touchStartRef.current = null;
        return;
      }

      if (zoom <= 1) {
        const endTouch = event.changedTouches[0];
        const deltaX = endTouch.clientX - start.x;
        const deltaY = endTouch.clientY - start.y;

        if (Math.abs(deltaX) > SWIPE_THRESHOLD && Math.abs(deltaX) > Math.abs(deltaY) * 1.5) {
          if (deltaX < 0 && currentIndex < total - 1) {
            setCurrentIndex((prev) => prev + 1);
          } else if (deltaX > 0 && currentIndex > 0) {
            setCurrentIndex((prev) => prev - 1);
          }
        }
      }

      touchStartRef.current = null;
      panStartRef.current = null;
    },
    [clearLongPress, currentIndex, total, zoom],
  );

  const lastTapRef = useRef<number>(0);
  const handleDoubleTap = useCallback(() => {
    const now = Date.now();
    if (now - lastTapRef.current < 300) {
      if (zoom > 1) {
        setZoom(1);
        setPan({ x: 0, y: 0 });
      } else {
        setZoom(2.5);
      }
      lastTapRef.current = 0;
    } else {
      lastTapRef.current = now;
    }
  }, [zoom]);

  const handleOverlayClick = useCallback(
    (event: React.MouseEvent) => {
      if (event.target === overlayRef.current) {
        onClose();
      }
    },
    [onClose],
  );

  const handleWheel = useCallback((event: React.WheelEvent) => {
    event.preventDefault();
    setZoom((prev) => {
      const nextZoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, prev - event.deltaY * 0.002));
      if (nextZoom <= 1) {
        setPan({ x: 0, y: 0 });
      }
      return nextZoom;
    });
  }, []);

  if (!images.length) {
    return <></>;
  }

  return (
    <div
      className="h5-image-viewer-overlay"
      onClick={handleOverlayClick}
      onTouchEnd={handleTouchEnd}
      onTouchMove={handleTouchMove}
      onTouchStart={handleTouchStart}
      onWheel={handleWheel}
      ref={overlayRef}
      role="dialog"
      aria-label={t("media.viewer")}
      aria-modal="true"
    >
      <button
        className="h5-image-viewer-close"
        onClick={onClose}
        type="button"
        aria-label={t("media.close")}
      >
        <CloseOutlined />
      </button>

      {hasMultiple ? (
        <div className="h5-image-viewer-counter">
          {currentIndex + 1} / {total}
        </div>
      ) : null}

      <div className="h5-image-viewer-content" onClick={handleDoubleTap}>
        <img
          ref={imgRef}
          alt=""
          className={`h5-image-viewer-img ${zoom > 1 ? "h5-image-viewer-img-zoomed" : ""}`.trim()}
          draggable={false}
          src={images[currentIndex]}
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
          }}
        />
      </div>

      {hasMultiple ? (
        <div className="h5-image-viewer-dots">
          {images.map((_, index) => (
            <span
              key={index}
              className={`h5-image-viewer-dot${index === currentIndex ? " h5-image-viewer-dot-active" : ""}`}
            />
          ))}
        </div>
      ) : null}

      {showTooltip ? <div className="h5-image-viewer-tooltip">{t("media.saveHint")}</div> : null}
    </div>
  );
}
