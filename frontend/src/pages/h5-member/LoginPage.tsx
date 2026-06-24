import { type JSX, type FormEvent, useState } from "react";

import { t } from "./i18n";

import { PasswordField } from "./sharedComponents";
import { h5ScrollableViewportStyle, useRootScrollUnlock } from "./useRootScrollUnlock";

function validatePhone(value: string): string {
  const cleaned = value.replace(/\s/g, "");
  if (!cleaned) return "";
  // 允许多国格式：纯数字或以 + 开头的国际号码，最少 6 位
  if (!/^(\+?\d+)$/.test(cleaned)) return t('validation.phoneDigitsOnly');
  if (cleaned.length < 6) return t('validation.phoneTooShort');
  return "";
}

function validatePassword(value: string): string {
  if (!value) return "";
  if (value.length < 6 || value.length > 64) return t('validation.passwordFormat');
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

type LoginPageProps = {
  page: "login" | "register";
  siteKey: string;
  loginPhone: string;
  loginPassword: string;
  loginPasswordVisible: boolean;
  registerPhone: string;
  registerPassword: string;
  registerPasswordVisible: boolean;
  registerConfirmPassword: string;
  registerConfirmPasswordVisible: boolean;
  rememberMe: boolean;
  onRememberMeChange: (value: boolean) => void;
  actionName: string | null;
  loginError: string | null;
  onLoginPhoneChange: (value: string) => void;
  onLoginPasswordChange: (value: string) => void;
  onLoginPasswordToggle: () => void;
  onRegisterPhoneChange: (value: string) => void;
  onRegisterPasswordChange: (value: string) => void;
  onRegisterPasswordToggle: () => void;
  onRegisterConfirmPasswordChange: (value: string) => void;
  onRegisterConfirmPasswordToggle: () => void;
  onLogin: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onRegister: (event: FormEvent<HTMLFormElement>) => Promise<void>;
  onNavigate: (path: string) => void;
};

export function LoginPage({
  page,
  siteKey,
  loginPhone,
  loginPassword,
  loginPasswordVisible,
  registerPhone,
  registerPassword,
  registerPasswordVisible,
  registerConfirmPassword,
  registerConfirmPasswordVisible,
  actionName,
  loginError,
  rememberMe,
  onRememberMeChange,
  onLoginPhoneChange,
  onLoginPasswordChange,
  onLoginPasswordToggle,
  onRegisterPhoneChange,
  onRegisterPasswordChange,
  onRegisterPasswordToggle,
  onRegisterConfirmPasswordChange,
  onRegisterConfirmPasswordToggle,
  onLogin,
  onRegister,
  onNavigate,
}: LoginPageProps): JSX.Element {
  useRootScrollUnlock();
  const isLoginPage = page === "login";
  const authBenefits = [
    t("auth.benefits.taskPackage"),
    t("auth.benefits.wallet"),
    t("auth.benefits.fragment"),
    t("auth.benefits.support"),
  ];

  const [loginPhoneError, setLoginPhoneError] = useState("");
  const [loginPhoneTouched, setLoginPhoneTouched] = useState(false);
  const [loginPasswordError, setLoginPasswordError] = useState("");
  const [loginPasswordTouched, setLoginPasswordTouched] = useState(false);
  const [registerPhoneError, setRegisterPhoneError] = useState("");
  const [registerPhoneTouched, setRegisterPhoneTouched] = useState(false);
  const [registerPasswordError, setRegisterPasswordError] = useState("");
  const [registerPasswordTouched, setRegisterPasswordTouched] = useState(false);
  const [registerConfirmError, setRegisterConfirmError] = useState("");
  const [registerConfirmTouched, setRegisterConfirmTouched] = useState(false);
  const [registerPasswordStrength, setRegisterPasswordStrength] = useState<{ bars: string[]; text: string }>({ bars: ["", "", ""], text: "" });

  function handleLoginPhoneChange(value: string): void {
    onLoginPhoneChange(value);
    setLoginPhoneError(validatePhone(value));
  }

  function handleLoginPhoneBlur(): void {
    setLoginPhoneTouched(true);
    setLoginPhoneError(validatePhone(loginPhone));
  }

  function handleLoginPasswordChange(value: string): void {
    onLoginPasswordChange(value);
    setLoginPasswordError(validatePassword(value));
  }

  function handleLoginPasswordBlur(): void {
    setLoginPasswordTouched(true);
    setLoginPasswordError(validatePassword(loginPassword));
  }

  function handleRegisterPhoneChange(value: string): void {
    onRegisterPhoneChange(value);
    setRegisterPhoneError(validatePhone(value));
  }

  function handleRegisterPhoneBlur(): void {
    setRegisterPhoneTouched(true);
    setRegisterPhoneError(validatePhone(registerPhone));
  }

  function handleRegisterPasswordChange(value: string): void {
    onRegisterPasswordChange(value);
    setRegisterPasswordError(validatePassword(value));
    setRegisterPasswordStrength(getPasswordStrength(value));
  }

  function handleRegisterPasswordBlur(): void {
    setRegisterPasswordTouched(true);
    setRegisterPasswordError(validatePassword(registerPassword));
  }

  function handleRegisterConfirmChange(value: string): void {
    onRegisterConfirmPasswordChange(value);
    if (value && value !== registerPassword) {
      setRegisterConfirmError(t('validation.confirmPasswordMismatch'));
    } else {
      setRegisterConfirmError("");
    }
  }

  function handleRegisterConfirmBlur(): void {
    setRegisterConfirmTouched(true);
    if (registerConfirmPassword && registerConfirmPassword !== registerPassword) {
      setRegisterConfirmError(t('validation.confirmPasswordMismatch'));
    } else {
      setRegisterConfirmError("");
    }
  }

  function handleLoginSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    setLoginPhoneTouched(true);
    setLoginPasswordTouched(true);
    const phoneErr = validatePhone(loginPhone);
    const passErr = validatePassword(loginPassword);
    setLoginPhoneError(phoneErr);
    setLoginPasswordError(passErr);
    if (phoneErr || passErr) return;
    void onLogin(event);
  }

  function handleRegisterSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    setRegisterPhoneTouched(true);
    setRegisterPasswordTouched(true);
    setRegisterConfirmTouched(true);
    const phoneErr = validatePhone(registerPhone);
    const passErr = validatePassword(registerPassword);
    const confirmErr = registerConfirmPassword !== registerPassword ? t('validation.confirmPasswordMismatch') : "";
    setRegisterPhoneError(phoneErr);
    setRegisterPasswordError(passErr);
    setRegisterConfirmError(confirmErr);
    if (phoneErr || passErr || confirmErr) return;
    void onRegister(event);
  }

  const loginPhoneErr = loginPhoneTouched ? loginPhoneError : "";
  const loginPassErr = loginPasswordTouched ? loginPasswordError : "";
  const registerPhoneErr = registerPhoneTouched ? registerPhoneError : "";
  const registerPassErr = registerPasswordTouched ? registerPasswordError : "";
  const registerConfirmErr = registerConfirmTouched ? registerConfirmError : "";

  return (
    <main className="h5-shell h5-member-auth-shell" style={h5ScrollableViewportStyle}>
      <section className="h5-member-auth-panel">
        <div className="h5-member-auth-logo">{siteKey.toUpperCase()}</div>
        <section className="h5-card h5-member-auth-card">
          <div className="h5-member-auth-brand-row">
            <span className="h5-member-auth-brand-pill">{t("shell.brandName")}</span>
            <span className="h5-member-auth-tip">{isLoginPage ? t("auth.loginByPassword") : t("auth.register")}</span>
          </div>
          <div className="h5-member-auth-heading">
            <strong>{isLoginPage ? t("auth.loginTitle") : t("auth.registerTitle")}</strong>
            <span>{t("auth.loginSubtitle")}</span>
          </div>
          <div className="h5-member-auth-benefits">
            {authBenefits.map((benefit) => (
              <span key={benefit}>{benefit}</span>
            ))}
          </div>
        </section>
        <section className="h5-card h5-member-auth-form-card">
          <p className="h5-member-auth-tip h5-member-auth-form-tip">
            {isLoginPage ? t("auth.loginTip") : t("auth.registerTip")}
          </p>
          <div className="h5-member-auth-switch">
            <button
              className={`h5-member-auth-tab ${page === "login" ? "h5-member-auth-tab-active" : ""}`}
              onClick={() => onNavigate("/h5/login")}
              type="button"
            >
              {t('auth.login')}
            </button>
            <button
              className={`h5-member-auth-tab ${page === "register" ? "h5-member-auth-tab-active" : ""}`}
              onClick={() => onNavigate("/h5/register")}
              type="button"
            >
              {t('auth.register')}
            </button>
          </div>

          {page === "login" ? (
            <form className="h5-form" onSubmit={(event) => handleLoginSubmit(event)}>
              <label>
                {t('auth.phoneNumber')}
                <input
                  className={loginPhoneErr ? "h5-field-input-error" : ""}
                  placeholder={t('auth.loginPhonePlaceholder')}
                  value={loginPhone}
                  onChange={(event) => handleLoginPhoneChange(event.target.value)}
                  onBlur={handleLoginPhoneBlur}
                />
              {loginPhoneErr ? <span className="h5-field-error">{loginPhoneErr}</span> : null}
              </label>

              <label>
                {t('auth.password')}
                  <PasswordField
                    placeholder={t('auth.loginPasswordPlaceholder')}
                    value={loginPassword}
                    visible={loginPasswordVisible}
                    onChange={handleLoginPasswordChange}
                    onToggle={onLoginPasswordToggle}
                    onBlur={handleLoginPasswordBlur}
                  />
                {loginPassErr ? <span className="h5-field-error">{loginPassErr}</span> : null}
              </label>

              <label className="h5-member-auth-remember-row">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(event) => onRememberMeChange(event.target.checked)}
                />
                <span>{t('auth.rememberMe')}</span>
              </label>

              {loginError ? <div className="h5-member-auth-error">{loginError}</div> : null}

              <button className="seed-button" disabled={actionName === "login"} type="submit">
                {actionName === "login" ? t('auth.loginSubmitting') : t('auth.login')}
              </button>

              <div className="h5-member-auth-link-row">
                <button
                  className="h5-member-auth-inline-link"
                  onClick={() => onNavigate("/h5/tickets/new")}
                  type="button"
                >
                  {t('auth.forgotPasswordLink')}
                </button>
              </div>
            </form>
          ) : (
            <form className="h5-form" onSubmit={(event) => handleRegisterSubmit(event)}>
              <label>
                {t('auth.phoneNumber')}
                <input
                  className={registerPhoneErr ? "h5-field-input-error" : ""}
                  placeholder={t('auth.registerPhonePlaceholder')}
                  value={registerPhone}
                  onChange={(event) => handleRegisterPhoneChange(event.target.value)}
                  onBlur={handleRegisterPhoneBlur}
                />
              {registerPhoneErr ? <span className="h5-field-error">{registerPhoneErr}</span> : null}
              </label>

              <label>
                {t('auth.password')}
                  <PasswordField
                    placeholder={t('auth.registerPasswordPlaceholder')}
                    value={registerPassword}
                    visible={registerPasswordVisible}
                    onChange={handleRegisterPasswordChange}
                    onToggle={onRegisterPasswordToggle}
                    onBlur={handleRegisterPasswordBlur}
                  />
              {registerPasswordStrength.text ? (
                <div>
                  <div className="h5-password-strength">
                    {registerPasswordStrength.bars.map((cls, i) => (
                      <span className={`h5-strength-bar ${cls}`} key={i} />
                    ))}
                  </div>
                  <span className="h5-strength-text">{registerPasswordStrength.text}</span>
                </div>
              ) : null}
              {registerPassErr ? <span className="h5-field-error">{registerPassErr}</span> : null}
              </label>
              <label>
                {t('auth.confirmPassword')}
                  <PasswordField
                    placeholder={t('auth.registerConfirmPlaceholder')}
                    value={registerConfirmPassword}
                    visible={registerConfirmPasswordVisible}
                    onChange={handleRegisterConfirmChange}
                    onToggle={onRegisterConfirmPasswordToggle}
                    onBlur={handleRegisterConfirmBlur}
                  />
              {registerConfirmErr ? <span className="h5-field-error">{registerConfirmErr}</span> : null}
              </label>
              <button className="seed-button" disabled={actionName === "register"} type="submit">
                {actionName === "register" ? t('auth.registerSubmitting') : t('auth.register')}
              </button>
            </form>
          )}
        </section>
        <section className="h5-card h5-member-auth-support-card">
          <div className="h5-member-auth-support-head">
            <div>
              <strong>{t("auth.demoAccount")}</strong>
              <span>{t("auth.demoAccountDesc")}</span>
            </div>
            <code>{siteKey.toUpperCase()}</code>
          </div>
          <div className="h5-member-auth-support-grid">
            <div className="h5-member-auth-support-item">
              <strong>{t("auth.forgotPassword")}</strong>
              <span>{t("auth.forgotPasswordDesc")}</span>
            </div>
            <div className="h5-member-auth-support-item">
              <strong>{isLoginPage ? t("auth.noAccount") : t("auth.hasAccount")}</strong>
              <span>{isLoginPage ? t("auth.noAccountDesc") : t("auth.hasAccountDesc")}</span>
            </div>
          </div>
          <div className="h5-member-auth-support-actions">
            <button className="seed-button seed-button-secondary" onClick={() => onNavigate("/h5/tickets/new")} type="button">
              {t("auth.newTicket")}
            </button>
            <button
              className="seed-button"
              onClick={() => onNavigate(isLoginPage ? "/h5/register" : "/h5/login")}
              type="button"
            >
              {isLoginPage ? t("auth.goRegister") : t("auth.goLogin")}
            </button>
          </div>
        </section>
      </section>
    </main>
  );
}
