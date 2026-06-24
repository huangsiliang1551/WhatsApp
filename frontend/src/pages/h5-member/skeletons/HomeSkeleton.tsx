import type { JSX } from "react";

export function HomeSkeleton(): JSX.Element {
  return (
    <div className="h5-skeleton-page">
      <div className="h5-skeleton-section">
        <div className="h5-skeleton-card h5-skeleton-card-home-hero">
          <div className="h5-skeleton-row h5-skeleton-row-home-title" />
          <div className="h5-skeleton-row h5-skeleton-row-home-subtitle" />
        </div>
        <div className="h5-skeleton-grid">
          <div className="h5-skeleton-card h5-skeleton-card-home-stat" />
          <div className="h5-skeleton-card h5-skeleton-card-home-stat" />
        </div>
      </div>
      <div className="h5-skeleton-section">
        <div className="h5-skeleton-row h5-skeleton-row-section-title" />
        <div className="h5-skeleton-card h5-skeleton-card-home-task h5-skeleton-card-stacked" />
        <div className="h5-skeleton-card h5-skeleton-card-home-task h5-skeleton-card-stacked" />
      </div>
    </div>
  );
}
