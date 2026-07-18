import { RouterProvider } from "@tanstack/react-router";
import { I18nProvider } from "../lib/i18n";
import { AppQueryProvider } from "./query";
import { router } from "./router";

export function AppProviders() {
  const locale = typeof navigator !== "undefined" && navigator.language?.toLowerCase().startsWith("zh") ? "zh" : "en";
  return <AppQueryProvider><I18nProvider locale={locale}><RouterProvider router={router} /></I18nProvider></AppQueryProvider>;
}
