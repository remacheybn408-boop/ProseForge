import { useState } from "react";
import { login, setupAdmin } from "../../lib/api/client";

export function Login({ onLoggedIn }: { onLoggedIn: () => void }) {
  const [setup, setSetup] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const submit = async () => {
    try {
      if (setup) await setupAdmin({ email, password });
      await login({ email, password });
      onLoggedIn();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to sign in"); }
  };
  return <section className="auth-card"><p className="eyebrow">WELCOME TO PROSEFORGE</p><h1>{setup ? "Create your owner account" : "Sign in to your writing space"}</h1><p className="auth-copy">Your projects, drafts, context and provider settings stay in your Docker-backed workspace.</p><label>Email<input value={email} onChange={event => setEmail(event.target.value)} type="email" autoComplete="email" /></label><label>Password<input value={password} onChange={event => setPassword(event.target.value)} type="password" autoComplete={setup ? "new-password" : "current-password"} /></label><button className="primary wide" onClick={submit}>{setup ? "Create account" : "Sign in"}</button><button className="link" onClick={() => { setSetup(!setup); setMessage(""); }}>{setup ? "I already have an account" : "First run? Create the owner account"}</button><p className="form-message" aria-live="polite">{message}</p></section>;
}
