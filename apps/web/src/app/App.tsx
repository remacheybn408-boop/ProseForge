import { useEffect, useState } from "react";
import "../styles/tokens.css";
import "../styles/views.css";
import "../styles/chat-shell.css";
import { getHealth, listProjects } from "../lib/api/client";
import { Login } from "../features/auth/Login";
import { AppProviders } from "./providers";
import { loadRuntimeConfig } from "./runtime";

export default function App() {
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);
  const check = () => {
    loadRuntimeConfig()
      .then(() => Promise.all([getHealth(), listProjects()]))
      .then(() => setAuthenticated(true))
      .catch(() => setAuthenticated(false));
  };
  useEffect(check, []);
  if (authenticated === null) return <main className="auth-shell"><p>Connecting to your Docker workspace…</p></main>;
  if (!authenticated) return <main className="auth-shell"><Login onLoggedIn={check} /></main>;
  return <AppProviders />;
}
