import type { JSX } from "react";

export function ListSkeleton({ count = 3 }: { count?: number }): JSX.Element {
  return (
    <div className="h5-skeleton-page">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="h5-skeleton-card" style={{ height: 80, marginBottom: 8 }}>
          <div className="h5-skeleton-row" style={{ width: '50%' }} />
          <div className="h5-skeleton-row" style={{ width: '30%', marginTop: 8 }} />
          <div className="h5-skeleton-row" style={{ width: '70%', marginTop: 8 }} />
        </div>
      ))}
    </div>
  );
}
