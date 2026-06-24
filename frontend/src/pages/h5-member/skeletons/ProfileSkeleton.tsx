import type { JSX } from "react";

export function ProfileSkeleton(): JSX.Element {
  return (
    <div className="h5-skeleton-page">
      <div className="h5-skeleton-card h5-skeleton-card-profile-hero">
        <div className="h5-skeleton-avatar" />
        <div className="h5-skeleton-profile-hero-copy">
          <div className="h5-skeleton-row h5-skeleton-row-profile-name" />
          <div className="h5-skeleton-row h5-skeleton-row-profile-meta" />
        </div>
      </div>
      <div className="h5-skeleton-card h5-skeleton-card-profile-summary h5-skeleton-card-stacked">
        <div className="h5-skeleton-row h5-skeleton-row-profile-summary-title" />
        <div className="h5-skeleton-row h5-skeleton-row-profile-summary-value" />
      </div>
      <div className="h5-skeleton-grid h5-skeleton-grid-profile-actions">
        <div className="h5-skeleton-card h5-skeleton-card-profile-action" />
        <div className="h5-skeleton-card h5-skeleton-card-profile-action" />
        <div className="h5-skeleton-card h5-skeleton-card-profile-action" />
      </div>
    </div>
  );
}
