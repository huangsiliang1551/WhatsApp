import { useEffect, type CSSProperties } from "react";

export const h5ScrollableViewportStyle: CSSProperties = {
  height: "var(--h5-visual-viewport-height, 100dvh)",
  display: "flex",
  flexDirection: "column",
  overflowX: "hidden",
  overflowY: "auto",
  WebkitOverflowScrolling: "touch",
  overscrollBehaviorY: "contain",
  touchAction: "pan-y",
};

export function useRootScrollUnlock(): void {
  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const root = document.documentElement;
    const viewport = window.visualViewport;

    if (!viewport) {
      root.style.removeProperty("--h5-visual-viewport-height");
      return;
    }

    const syncViewportHeight = (): void => {
      root.style.setProperty("--h5-visual-viewport-height", `${Math.round(viewport.height)}px`);
    };

    syncViewportHeight();
    viewport.addEventListener("resize", syncViewportHeight);
    viewport.addEventListener("scroll", syncViewportHeight);

    return () => {
      viewport.removeEventListener("resize", syncViewportHeight);
      viewport.removeEventListener("scroll", syncViewportHeight);
      root.style.removeProperty("--h5-visual-viewport-height");
    };
  }, []);
}
