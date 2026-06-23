import type { JSX } from "react";

export function ProfileSkeleton(): JSX.Element {
  return (
    <div className="h5-skeleton-page">
      <div className="h5-skeleton-card" style={{ height: 120, display: 'flex', alignItems: 'center', gap: 16 }}>
        <div className="h5-skeleton-avatar" />
        <div style={{ flex: 1 }}>
          <div className="h5-skeleton-row" style={{ width: '40%' }} />
          <div className="h5-skeleton-row" style={{ width: '60%', marginTop: 8 }} />
        </div>
      </div>
      <div className="h5-skeleton-card" style={{ height: 80, marginTop: 8 }}>
        <div className="h5-skeleton-row" style={{ width: '30%' }} />
        <div className="h5-skeleton-row" style={{ width: '50%', marginTop: 8 }} />
      </div>
      <div className="h5-skeleton-grid" style={{ marginTop: 8 }}>
        <div className="h5-skeleton-card" style={{ height: 60 }} />
        <div className="h5-skeleton-card" style={{ height: 60 }} />
        <div className="h5-skeleton-card" style={{ height: 60 }} />
      </div>
    </div>
  );
}
