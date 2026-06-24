import { type JSX } from "react";
import { AuditOutlined } from "@ant-design/icons";

import type { H5MemberVerificationRequest, H5MemberVerificationSummary } from "../../services/h5Member";
import {
  formatTimestamp,
  getVerificationRequestStatusLabel,
  getVerificationRequestTone,
  getVerificationRequestTypeLabel,
  getVerificationStatusLabel,
} from "./sharedUtils";
import { CompactListRow, DetailGrid, EmptyStateCard, SectionHeader } from "./sharedComponents";
import { t } from "./i18n";
import { MediaUploader } from "./MediaUploader";
import { DetailSkeleton } from "./skeletons";

type VerificationPageProps = {
  effectiveVerificationSummary: H5MemberVerificationSummary;
  verificationRequests: H5MemberVerificationRequest[];
  verificationRequestDetail: H5MemberVerificationRequest | null;
  verificationHistory: H5MemberVerificationRequest[];
  verificationNotes: string;
  focusedVerificationRequest: H5MemberVerificationRequest | null;
  canSubmitVerificationRequest: boolean;
  verificationActionId: string | null;
  siteKey: string;
  onNavigate: (path: string) => void;
  onSubmitVerification: () => Promise<void>;
  onOpenVerificationRequest: (requestId: string) => Promise<void>;
  onVerificationNotesChange: (value: string) => void;
  verificationName: string;
  verificationIdNumber: string;
  actionName: string | null;
  onSubmitVerificationApi: () => Promise<void>;
  onVerificationNameChange: (value: string) => void;
  onVerificationIdNumberChange: (value: string) => void;
  onVerificationPhotoFilesChange: (files: File[]) => void;
  loading?: boolean;
};

function getStatusTone(status: string): "default" | "active" | "success" | "danger" {
  if (status === "pending" || status === "under_review") return "active";
  if (status === "approved" || status === "verified") return "success";
  if (status === "rejected") return "danger";
  return "default";
}

function getStatusHeadline(status: string): string {
  if (status === "pending" || status === "under_review") return t("verification.statusUnderReview");
  if (status === "approved" || status === "verified") return t("verification.statusApproved");
  if (status === "rejected") return t("verification.statusRejected");
  return t("verification.statusNotSubmitted");
}

export function VerificationPage({
  effectiveVerificationSummary,
  verificationRequests: _verificationRequests,
  verificationRequestDetail: _verificationRequestDetail,
  verificationHistory,
  verificationNotes,
  focusedVerificationRequest,
  canSubmitVerificationRequest,
  verificationActionId,
  siteKey: _siteKey,
  onNavigate: _onNavigate,
  onSubmitVerification: _onSubmitVerification,
  onOpenVerificationRequest,
  onVerificationNotesChange,
  verificationName,
  verificationIdNumber,
  actionName,
  onSubmitVerificationApi,
  onVerificationNameChange,
  onVerificationIdNumberChange,
  onVerificationPhotoFilesChange,
  loading = false,
}: VerificationPageProps): JSX.Element {
  if (loading) return <DetailSkeleton />;

  const isSubmitting = actionName === "verification-api-submit";
  const statusFlow = effectiveVerificationSummary.currentStatus;
  const statusTone = getStatusTone(statusFlow);
  const statusHeadline = getStatusHeadline(statusFlow);
  const statusDescription = effectiveVerificationSummary.hasActiveRequest
    ? t("verification.hasActiveRequest")
    : t("verification.noActiveRequest");
  const latestStatusRequest = [focusedVerificationRequest, effectiveVerificationSummary.activeRequest, ...verificationHistory]
    .filter((request): request is H5MemberVerificationRequest => Boolean(request))
    .reduce<H5MemberVerificationRequest | null>((latest, request) => {
      if (!latest) return request;
      return new Date(request.updatedAt).getTime() > new Date(latest.updatedAt).getTime() ? request : latest;
    }, null);
  const latestDocumentCount = latestStatusRequest?.documents.length ?? 0;
  const hasIdentityReady = verificationName.trim().length > 0;

  const prepChecklistCard = (
    <article className="h5-card h5-member-verification-prep-card">
      <SectionHeader meta={t("verification.prepMeta")} title={t("verification.prepTitle")} />
      <div className="h5-card-stack">
        <CompactListRow
          badge={hasIdentityReady ? t("verification.yes") : t("verification.no")}
          sideNote={t("verification.requestType")}
          subtitle={t("verification.prepIdentityDesc")}
          title={t("verification.prepIdentityTitle")}
          tone={hasIdentityReady ? "success" : "default"}
        />
        <CompactListRow
          badge={latestDocumentCount > 0 ? t("verification.documentsCount", { count: latestDocumentCount }) : t("verification.waitingUpload")}
          sideNote={t("verification.photoLabel")}
          subtitle={t("verification.prepPhotoDesc")}
          title={t("verification.prepPhotoTitle")}
          tone={latestDocumentCount > 0 ? "success" : "active"}
        />
        <CompactListRow
          badge={statusHeadline}
          sideNote={latestStatusRequest ? formatTimestamp(latestStatusRequest.updatedAt) : t("verification.noRecord")}
          subtitle={t("verification.prepReviewDesc")}
          title={t("verification.prepReviewTitle")}
          tone={statusTone}
        />
      </div>
    </article>
  );

  const currentRequestCard = (
    <article className="h5-card">
      <SectionHeader
        meta={
          focusedVerificationRequest
            ? getVerificationRequestStatusLabel(focusedVerificationRequest.status)
            : t("verification.noActiveTitle")
        }
        title={t("verification.currentRequest")}
      />
      {focusedVerificationRequest ? (
        <div className="h5-card-stack">
          <CompactListRow
            title={getVerificationRequestTypeLabel(focusedVerificationRequest.requestType)}
            badge={getVerificationRequestStatusLabel(focusedVerificationRequest.status)}
            meta={t("verification.submittedAt", { time: formatTimestamp(focusedVerificationRequest.createdAt) })}
            sideNote={t("verification.documentsCount", { count: focusedVerificationRequest.documents.length })}
            tone={getVerificationRequestTone(focusedVerificationRequest.status)}
          />
          {focusedVerificationRequest.notes ? (
            <div className="h5-member-ticket-message">
              <strong>{t("verification.requestNotes")}</strong>
              <p>{focusedVerificationRequest.notes}</p>
            </div>
          ) : null}
          {focusedVerificationRequest.reviewNote ? (
            <div className="h5-member-ticket-message">
              <strong>{t("verification.reviewNotes")}</strong>
              <p>{focusedVerificationRequest.reviewNote}</p>
            </div>
          ) : null}
          <div className="h5-card-stack">
            {focusedVerificationRequest.documents.length > 0 ? (
              focusedVerificationRequest.documents.map((document) => (
                <CompactListRow
                  key={document.id}
                  title={document.fileName}
                  meta={document.storageKey ?? t("verification.waitingUpload")}
                  sideNote={formatTimestamp(document.createdAt)}
                />
              ))
            ) : (
              <CompactListRow title={t("verification.noDocuments")} meta={t("verification.noDocumentsDesc")} />
            )}
          </div>
        </div>
      ) : (
        <EmptyStateCard
          action={
            <button
              className="h5-secondary-button"
              onClick={() => onVerificationNotesChange(t("verification.exampleNote"))}
              type="button"
            >
              {t("verification.fillExample")}
            </button>
          }
          description={t("verification.noRequestDesc")}
          icon={<AuditOutlined />}
          title={t("verification.noRequestTitle")}
        />
      )}
    </article>
  );

  const submitRequestCard = canSubmitVerificationRequest ? (
    <article className="h5-card">
      <SectionHeader meta={t("verification.contactSupport")} title={t("verification.submitRequest")} />
      <form
        className="h5-form h5-member-verification-form"
        onSubmit={(event) => {
          event.preventDefault();
          void onSubmitVerificationApi();
        }}
      >
        <label>
          {t("verification.requestType")}
          <input disabled value={t("verification.identity")} />
        </label>
        <label>
          {t("verification.nameLabel")}
          <input
            value={verificationName}
            onChange={(event) => onVerificationNameChange(event.target.value)}
            placeholder={t("verification.namePlaceholder")}
            required
          />
        </label>
        <label>
          {t("verification.idNumberLabel")}
          <input
            value={verificationIdNumber}
            onChange={(event) => onVerificationIdNumberChange(event.target.value)}
            placeholder={t("verification.idNumberPlaceholder")}
          />
        </label>
        <label className="h5-member-verification-upload-field">
          <span className="h5-member-verification-upload-label">{t("verification.photoLabel")}</span>
          <MediaUploader
            accept="image/*"
            maxSizeMB={5}
            multiple
            onUpload={(files) => {
              onVerificationPhotoFilesChange(files.map((file) => file.file));
            }}
            preview
            compress
          />
        </label>
        <label>
          {t("verification.notes")}
          <textarea
            rows={4}
            value={verificationNotes}
            onChange={(event) => onVerificationNotesChange(event.target.value)}
            placeholder={t("verification.notesPlaceholder")}
          />
        </label>
        <p className="h5-member-verification-hint">{t("verification.uploadNote")}</p>
        <div className="h5-member-card-actions">
          <button
            className="h5-secondary-button"
            onClick={() => _onNavigate("/h5/tickets/new")}
            type="button"
          >
            {t("verification.openSupport")}
          </button>
          <button
            className="h5-primary-button"
            disabled={isSubmitting || !verificationName.trim()}
            type="submit"
          >
            {isSubmitting ? t("verification.submitting") : t("verification.submitRequestBtn")}
          </button>
        </div>
      </form>
    </article>
  ) : null;

  return (
    <section className="h5-card-stack">
      <article className="h5-card">
        <SectionHeader
          meta={getVerificationStatusLabel(statusFlow)}
          title={t("verification.verificationStatus")}
        />
        <DetailGrid
          items={[
            { label: t("verification.currentStatus"), value: getVerificationRequestStatusLabel(statusFlow) },
            {
              label: t("verification.pendingApplications"),
              value: effectiveVerificationSummary.hasActiveRequest ? t("verification.yes") : t("verification.no"),
            },
            { label: t("verification.historyCount"), value: String(verificationHistory.length) },
            {
              label: t("verification.lastUpdate"),
              value: latestStatusRequest ? formatTimestamp(latestStatusRequest.updatedAt) : t("verification.noRecord"),
            },
          ]}
        />
        <div className={`h5-member-verification-status-flow h5-member-verification-status-flow-${statusTone}`}>
          <div className="h5-member-verification-status-line">
            <strong>{statusHeadline}</strong>
            <span>{statusDescription}</span>
          </div>
          <p className="h5-member-verification-hint">{t("verification.uploadNote")}</p>
        </div>
      </article>
      {prepChecklistCard}
      {focusedVerificationRequest ? currentRequestCard : null}
      {submitRequestCard}
      {!focusedVerificationRequest ? currentRequestCard : null}

      <article className="h5-card">
        <SectionHeader
          meta={t("verification.historyItems", { count: verificationHistory.length })}
          title={t("verification.applicationHistory")}
        />
        <div className="h5-card-stack">
          {verificationHistory.length > 0 ? (
            verificationHistory.map((request) => (
              <CompactListRow
                actionLabel={verificationActionId === `detail:${request.id}` ? t("verification.loading") : t("verification.view")}
                badge={getVerificationRequestStatusLabel(request.status)}
                key={request.id}
                meta={t("verification.documentsCount", { count: request.documents.length })}
                onClick={() => void onOpenVerificationRequest(request.id)}
                sideNote={formatTimestamp(request.updatedAt)}
                subtitle={request.reviewNote ?? request.notes ?? t("verification.noNote")}
                title={getVerificationRequestTypeLabel(request.requestType)}
                tone={getVerificationRequestTone(request.status)}
              />
            ))
          ) : (
            <EmptyStateCard
              description={t("verification.noHistoryDesc")}
              icon={<AuditOutlined />}
              title={t("verification.noHistoryTitle")}
            />
          )}
        </div>
      </article>
    </section>
  );
}
