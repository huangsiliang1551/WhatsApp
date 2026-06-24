import type { JSX } from "react";

export function DetailSkeleton(): JSX.Element {
  return (
    <div className="h5-skeleton-page">
      <div className="h5-skeleton-card h5-skeleton-card-detail-hero">
        <div className="h5-skeleton-row h5-skeleton-row-detail-label" />
        <div className="h5-skeleton-row h5-skeleton-row-detail-heading" />
        <div className="h5-skeleton-row h5-skeleton-row-detail-meta" />
      </div>
      <div className="h5-skeleton-card h5-skeleton-card-detail-section h5-skeleton-card-stacked">
        <div className="h5-skeleton-row h5-skeleton-row-detail-section-title" />
        <div className="h5-skeleton-row h5-skeleton-row-detail-section-body" />
        <div className="h5-skeleton-row h5-skeleton-row-detail-section-foot" />
      </div>
    </div>
  );
}
