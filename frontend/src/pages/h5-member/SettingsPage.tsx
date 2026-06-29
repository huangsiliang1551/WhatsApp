import { type JSX, type ChangeEvent, type FormEvent, useState } from "react";
import { UserOutlined } from "@ant-design/icons";

import type { H5HomeDashboard } from "../../services/h5Member";
import { CompactListRow, DetailGrid, PasswordField, SectionHeader } from "./sharedComponents";
import { t } from "./i18n";
import { ProfileSkeleton } from "./skeletons";
import { formatTimestamp, getVerificationStatusLabel } from "./sharedUtils";

function validatePhone(value: string): string {
  const cleaned = value.replace(/\s/g, "");
  if (!cleaned) return "";
  if (!/^\d+$/.test(cleaned)) return t('validation.phoneDigitsOnly');
  if (cleaned.length < 8) return t('validation.phoneTooShort');
  return "";
}

function getPasswordStrength(password: string): { bars: string[]; text: string } {
  const bars = ["", "", ""];
  if (!password) return { bars: ["", "", ""], text: "" };
  let score = 0;
  if (password.length >= 8) score++;
  if (password.length >= 12) score++;
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score++;
  if (/\d/.test(password)) score++;
  if (/[^a-zA-Z0-9]/.test(password)) score++;
  if (score <= 1) {
    bars[0] = "h5-strength-bar-weak";
    return { bars, text: t('validation.passwordWeak') };
  }
  if (score <= 3) {
    bars[0] = "h5-strength-bar-medium";
    bars[1] = "h5-strength-bar-medium";
    return { bars, text: t('validation.passwordMedium') };
  }
  bars[0] = "h5-strength-bar-strong";
  bars[1] = "h5-strength-bar-strong";
  bars[2] = "h5-strength-bar-strong";
  return { bars, text: t('validation.passwordStrong') };
}

type SettingsPageProps = {
  dashboard: H5HomeDashboard;
  settingsPhone: string;
  settingsAvatarUrl: string | null;
  settingsCurrentPassword: string;
  settingsNextPassword: string;
  settingsConfirmPassword: string;
  settingsCurrentPasswordVisible: boolean;
  settingsNextPasswordVisible: boolean;
  settingsConfirmPasswordVisible: boolean;
  actionName: string | null;
  onPhoneChange: (value: string) => void;
  onAvatarChange: (event: ChangeEvent<HTMLInputElement>) => Promise<void>;
  onSaveProfile: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onCurrentPasswordChange: (value: string) => void;
  onCurrentPasswordToggle: () => void;
  onNextPasswordChange: (value: string) => void;
  onNextPasswordToggle: () => void;
  onConfirmPasswordChange: (value: string) => void;
  onConfirmPasswordToggle: () => void;
  onChangePassword: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  loading?: boolean;
};

export function SettingsPage({
  dashboard,
  settingsPhone,
  settingsAvatarUrl,
  settingsCurrentPassword,
  settingsNextPassword,
  settingsConfirmPassword,
  settingsCurrentPasswordVisible,
  settingsNextPasswordVisible,
  settingsConfirmPasswordVisible,
  actionName,
  onPhoneChange,
  onAvatarChange,
  onSaveProfile,
  onCurrentPasswordChange,
  onCurrentPasswordToggle,
  onNextPasswordChange,
  onNextPasswordToggle,
  onConfirmPasswordChange,
  onConfirmPasswordToggle,
  onChangePassword,
  loading = false,
}: SettingsPageProps): JSX.Element {
  if (loading) return <ProfileSkeleton />;
  const [phoneError, setPhoneError] = useState("");
  const [newPasswordStrength, setNewPasswordStrength] = useState<{ bars: string[]; text: string }>({ bars: ["", "", ""], text: "" });
  const [profileSaveSuccess, setProfileSaveSuccess] = useState(false);
  const [profileSaveError, setProfileSaveError] = useState<string | null>(null);
  const [passwordChangeSuccess, setPasswordChangeSuccess] = useState(false);
  const [passwordChangeError, setPasswordChangeError] = useState<string | null>(null);

  function handlePhoneChange(value: string): void {
    onPhoneChange(value);
    setPhoneError(validatePhone(value));
  }

  function handleNextPasswordChange(value: string): void {
    onNextPasswordChange(value);
    setNewPasswordStrength(getPasswordStrength(value));
    setPasswordChangeSuccess(false);
    setPasswordChangeError(null);
  }

  async function handleSaveProfile(event: FormEvent<HTMLFormElement>): Promise<void> {
    setProfileSaveSuccess(false);
    setProfileSaveError(null);
    try {
      await onSaveProfile(event);
      setProfileSaveSuccess(true);
    } catch {
      // Error handled by app-level state
    }
  }

  async function handleChangePasswordSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    setPasswordChangeSuccess(false);
    setPasswordChangeError(null);
    if (settingsNextPassword !== settingsConfirmPassword) {
      setPasswordChangeError(t('validation.passwordMismatch'));
      return;
    }
    try {
      await onChangePassword(event);
      setPasswordChangeSuccess(true);
    } catch {
      // Error handled by app-level state
    }
  }

  const overviewItems = [
    { label: t('settings.overviewIdentityLabel'), value: dashboard.member.displayName || dashboard.member.accountIdMasked },
    { label: t('settings.overviewPhoneLabel'), value: settingsPhone || dashboard.member.phone || "--" },
    { label: t('settings.overviewVerificationLabel'), value: getVerificationStatusLabel(dashboard.verification.currentStatus) },
    { label: t('settings.overviewMemberSinceLabel'), value: formatTimestamp(dashboard.member.createdAt) },
  ];

  return (
    <section className="h5-card-stack">
      <article className="h5-card h5-member-settings-overview-card">
        <SectionHeader meta={t('settings.overviewMeta')} title={t('settings.overviewTitle')} />
        <DetailGrid items={overviewItems} />
      </article>

      <article className="h5-card">
        <SectionHeader meta={t('settings.profileManagement')} title={t('settings.title')} />
        <form className="h5-form h5-card-stack" onSubmit={(event) => void handleSaveProfile(event)}>
          <div className="h5-member-settings-avatar-row">
            <div className="h5-member-settings-avatar-preview" aria-hidden="true">
              {settingsAvatarUrl ? (
                <img alt={t('settings.avatarPreview')} className="h5-member-profile-avatar-image" src={settingsAvatarUrl} />
              ) : (
                <UserOutlined />
              )}
            </div>
            <div className="h5-member-settings-avatar-copy">
              <strong>{t('settings.avatarUpload')}</strong>
              <span>{t('settings.avatarHint')}</span>
              <label className="seed-button seed-button-secondary h5-member-settings-upload-label">
                {t('settings.chooseAvatar')}
                <input accept="image/*" className="h5-member-settings-upload-input" onChange={(event) => void onAvatarChange(event)} type="file" />
              </label>
            </div>
          </div>
          <label>
            {t('settings.phoneNumber')}
            <input
              inputMode="numeric"
              placeholder={t('settings.phonePlaceholder')}
              value={settingsPhone}
              onChange={(event) => handlePhoneChange(event.target.value)}
              className={phoneError ? "h5-field-input-error" : ""}
            />
          </label>
          {phoneError ? <span className="h5-field-error">{phoneError}</span> : null}
          <button className="h5-primary-button" disabled={actionName === "settings-profile" || actionName === "settings-avatar"} type="submit">
            {actionName === "settings-profile" || actionName === "settings-avatar" ? t('settings.saving') : t('settings.saveProfile')}
          </button>
          {profileSaveSuccess ? <span className="h5-field-success">{t("notification.profileUpdated")}</span> : null}
          {profileSaveError ? <span className="h5-field-error">{profileSaveError}</span> : null}
        </form>
      </article>

      <article className="h5-card h5-member-settings-checklist-card">
        <SectionHeader meta={t('settings.securityChecklistMeta')} title={t('settings.securityChecklistTitle')} />
        <div className="h5-card-stack">
          <CompactListRow
            title={t('settings.securityPhoneTitle')}
            subtitle={t('settings.securityPhoneDesc')}
            value={settingsPhone || dashboard.member.phone || "--"}
          />
          <CompactListRow
            title={t('settings.securityPasswordTitle')}
            subtitle={t('settings.securityPasswordDesc')}
            value={t('settings.securityPasswordValue')}
            tone="active"
          />
          <CompactListRow
            title={t('settings.securityReviewTitle')}
            subtitle={t('settings.securityReviewDesc')}
            value={getVerificationStatusLabel(dashboard.verification.currentStatus)}
            tone={dashboard.verification.currentStatus === "approved" || dashboard.verification.currentStatus === "verified" ? "success" : "default"}
          />
        </div>
      </article>

      <article className="h5-card">
        <SectionHeader meta={t('settings.securitySettings')} title={t('settings.changePassword')} />
        <form className="h5-form h5-card-stack" onSubmit={(event) => void handleChangePasswordSubmit(event)}>
          <label>
            {t('settings.currentPassword')}
            <PasswordField
              onChange={onCurrentPasswordChange}
              onToggle={onCurrentPasswordToggle}
              placeholder={t('settings.currentPasswordPlaceholder')}
              value={settingsCurrentPassword}
              visible={settingsCurrentPasswordVisible}
            />
          </label>
          <label>
            {t('settings.newPassword')}
            <PasswordField
              onChange={handleNextPasswordChange}
              onToggle={onNextPasswordToggle}
              placeholder={t('settings.newPasswordPlaceholder')}
              value={settingsNextPassword}
              visible={settingsNextPasswordVisible}
            />
          {newPasswordStrength.text ? (
            <div>
              <div className="h5-password-strength">
                {newPasswordStrength.bars.map((cls, i) => (
                  <span className={`h5-strength-bar ${cls}`} key={i} />
                ))}
              </div>
              <span className="h5-strength-text">{newPasswordStrength.text}</span>
            </div>
          ) : null}
          </label>
          <label>
            {t('settings.confirmNewPassword')}
            <PasswordField
              onChange={onConfirmPasswordChange}
              onToggle={onConfirmPasswordToggle}
              placeholder={t('settings.confirmNewPasswordPlaceholder')}
              value={settingsConfirmPassword}
              visible={settingsConfirmPasswordVisible}
            />
          </label>
          {passwordChangeError ? <span className="h5-field-error">{passwordChangeError}</span> : null}
          <button className="h5-primary-button" disabled={actionName === "settings-password"} type="submit">
            {actionName === "settings-password" ? t('settings.modifying') : t('settings.modifyPassword')}
          </button>
          {passwordChangeSuccess ? <span className="h5-field-success">{t("notification.passwordChanged")}</span> : null}
        </form>
      </article>
    </section>
  );
}
