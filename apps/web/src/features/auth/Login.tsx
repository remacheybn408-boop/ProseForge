import { useState } from "react";
import { login, setupAdmin } from "../../lib/api/client";
import { useLanguage } from "../../lib/i18n";

export function Login({ onLoggedIn }: { onLoggedIn: () => void }) {
  const { t } = useLanguage();
  const [setup, setSetup] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const submit = async () => {
    try {
      if (setup) await setupAdmin({ email, password });
      await login({ email, password });
      onLoggedIn();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to sign in");
    }
  };
  return <section className="auth-card"><p className="eyebrow">{t("appName")}</p><h1>{setup ? t("createOwner") : t("signInTitle")}</h1><p className="auth-copy">{t("authIntro")}</p><label>Email<input value={email} onChange={event => setEmail(event.target.value)} type="email" autoComplete="email" /></label><label>Password<input value={password} onChange={event => setPassword(event.target.value)} type="password" autoComplete={setup ? "new-password" : "current-password"} /></label><button className="primary wide" onClick={submit}>{setup ? t("createOwner") : t("signIn")}</button><button className="link" onClick={() => { setSetup(!setup); setMessage(""); }}>{setup ? t("alreadyAccount") : t("firstRun")}</button><p className="form-message" aria-live="polite">{message}</p></section>;
}
