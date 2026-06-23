import type { JSX } from "react";

export function HomeSkeleton(): JSX.Element {
  return (
    <div className="h5-skeleton-page">
      <div className="h5-skeleton-section">
        <div className="h5-skeleton-card" style={{ height: 100 }}>
          <div className="h5-skeleton-row" style={{ width: '40%' }} />
          <div className="h5-skeleton-row" style={{ width: '60%', marginTop: 12 }} />
        </div>
        <div className="h5-skeleton-grid">
          <div className="h5-skeleton-card" style={{ height: 80 }} />
          <div className="h5-skeleton-card" style={{ height: 80 }} />
        </div>
      </div>
      <div className="h5-skeleton-section">
        <div className="h5-skeleton-row" style={{ width: '30%' }} />
        <div className="h5-skeleton-card" style={{ height: 120, marginTop: 8 }} />
        <div className="h5-skeleton-card" style={{ height: 120, marginTop: 8 }} />
      </div>
    </div>
  );
}
