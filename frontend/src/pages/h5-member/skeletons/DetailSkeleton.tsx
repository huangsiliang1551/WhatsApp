import type { JSX } from "react";

export function DetailSkeleton(): JSX.Element {
  return (
    <div className="h5-skeleton-page">
      <div className="h5-skeleton-card" style={{ height: 180 }}>
        <div className="h5-skeleton-row" style={{ width: '30%' }} />
        <div className="h5-skeleton-row" style={{ width: '60%', marginTop: 12, height: 24 }} />
        <div className="h5-skeleton-row" style={{ width: '40%', marginTop: 12 }} />
      </div>
      <div className="h5-skeleton-card" style={{ height: 140, marginTop: 8 }}>
        <div className="h5-skeleton-row" style={{ width: '40%' }} />
        <div className="h5-skeleton-row" style={{ width: '80%', marginTop: 8 }} />
        <div className="h5-skeleton-row" style={{ width: '60%', marginTop: 8 }} />
      </div>
    </div>
  );
}
