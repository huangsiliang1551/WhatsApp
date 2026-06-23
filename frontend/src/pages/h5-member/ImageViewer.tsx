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

  // Keyboard handling
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      switch (e.key) {
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

  // Reset zoom on image change
  useEffect(() => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
    setShowTooltip(false);
  }, [currentIndex]);

  // Long press handling
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

  // Touch handlers
  const handleTouchStart = useCallback(
    (e: React.TouchEvent) => {
      if (e.touches.length === 1) {
        const touch = e.touches[0];
        touchStartRef.current = { x: touch.clientX, y: touch.clientY, time: Date.now() };
        panStartRef.current = { x: pan.x, y: pan.y };
        startLongPress();
      } else if (e.touches.length === 2) {
        clearLongPress();
        const dx = e.touches[0].clientX - e.touches[1].clientX;
        const dy = e.touches[0].clientY - e.touches[1].clientY;
        pinchRef.current = { dist: Math.hypot(dx, dy), zoom };
        touchStartRef.current = null;
      }
    },
    [zoom, pan, startLongPress, clearLongPress],
  );

  const handleTouchMove = useCallback(
    (e: React.TouchEvent) => {
      if (e.touches.length === 2 && pinchRef.current) {
        const dx = e.touches[0].clientX - e.touches[1].clientX;
        const dy = e.touches[0].clientY - e.touches[1].clientY;
        const dist = Math.hypot(dx, dy);
        const newZoom = Math.max(
          MIN_ZOOM,
          Math.min(MAX_ZOOM, (dist / pinchRef.current.dist) * pinchRef.current.zoom),
        );
        setZoom(newZoom);
        if (newZoom <= 1) {
          setPan({ x: 0, y: 0 });
        }
      } else if (e.touches.length === 1 && touchStartRef.current && zoom > 1) {
        const touch = e.touches[0];
        const deltaX = touch.clientX - touchStartRef.current.x;
        const deltaY = touch.clientY - touchStartRef.current.y;
        setPan({
          x: (panStartRef.current?.x ?? 0) + deltaX,
          y: (panStartRef.current?.y ?? 0) + deltaY,
        });
        clearLongPress();
      } else if (e.touches.length === 1) {
        clearLongPress();
      }
    },
    [zoom, clearLongPress],
  );

  const handleTouchEnd = useCallback(
    (e: React.TouchEvent) => {
      clearLongPress();
      pinchRef.current = null;

      const start = touchStartRef.current;
      if (!start) {
        touchStartRef.current = null;
        return;
      }

      // Detect swipe only when not zoomed
      if (zoom <= 1) {
        const endTouch = e.changedTouches[0];
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
    [zoom, currentIndex, total, clearLongPress],
  );

  // Double-tap to toggle zoom
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

  // Click outside image to close
  const handleOverlayClick = useCallback(
    (e: React.MouseEvent) => {
      if (e.target === overlayRef.current) {
        onClose();
      }
    },
    [onClose],
  );

  // Mouse wheel zoom
  const handleWheel = useCallback(
    (e: React.WheelEvent) => {
      e.preventDefault();
      setZoom((prev) => {
        const newZoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, prev - e.deltaY * 0.002));
        if (newZoom <= 1) setPan({ x: 0, y: 0 });
        return newZoom;
      });
    },
    [],
  );

  if (!images.length) return <></>;

  return (
    <div
      className="h5-image-viewer-overlay"
      onClick={handleOverlayClick}
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
      onWheel={handleWheel}
      ref={overlayRef}
      role="dialog"
      aria-modal="true"
      aria-label={t("media.viewer")}
    >
      {/* Close button */}
      <button
        className="h5-image-viewer-close"
        onClick={onClose}
        type="button"
        aria-label={t("media.close")}
      >
        ✕
      </button>

      {/* Image counter */}
      {hasMultiple && (
        <div className="h5-image-viewer-counter">
          {currentIndex + 1} / {total}
        </div>
      )}

      {/* Image */}
      <div
        className="h5-image-viewer-content"
        onClick={handleDoubleTap}
      >
        <img
          ref={imgRef}
          className="h5-image-viewer-img"
          src={images[currentIndex]}
          alt=""
          draggable={false}
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            cursor: zoom > 1 ? "grab" : "default",
          }}
        />
      </div>

      {/* Dot indicators */}
      {hasMultiple && (
        <div className="h5-image-viewer-dots">
          {images.map((_, i) => (
            <span
              key={i}
              className={`h5-image-viewer-dot${i === currentIndex ? " h5-image-viewer-dot-active" : ""}`}
            />
          ))}
        </div>
      )}

      {/* Long press tooltip */}
      {showTooltip && (
        <div className="h5-image-viewer-tooltip">
          {t("media.saveHint")}
        </div>
      )}
    </div>
  );
}
