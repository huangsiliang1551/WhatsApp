import type { JSX } from "react";

export function ListSkeleton({ count = 3 }: { count?: number }): JSX.Element {
  return (
    <div className="h5-skeleton-page">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="h5-skeleton-card h5-skeleton-card-list-item">
          <div className="h5-skeleton-row h5-skeleton-row-list-title" />
          <div className="h5-skeleton-row h5-skeleton-row-list-meta" />
          <div className="h5-skeleton-row h5-skeleton-row-list-body" />
        </div>
      ))}
    </div>
  );
}
