import { RouterProvider } from "@tanstack/react-router";
import { I18nProvider, type Locale } from "../lib/i18n";
import { AppQueryProvider } from "./query";
import { router } from "./router";

export function AppProviders() {
  const stored = typeof window !== "undefined" ? window.localStorage.getItem("proseforge.language") : null;
  const locale: Locale = stored === "zh" || stored === "en" ? stored : typeof navigator !== "undefined" && navigator.language?.toLowerCase().startsWith("zh") ? "zh" : "en";
  return <AppQueryProvider><I18nProvider locale={locale}><RouterProvider router={router} /></I18nProvider></AppQueryProvider>;
}
