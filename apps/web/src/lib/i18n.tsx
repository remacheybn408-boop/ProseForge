import { createContext, useContext } from "react";
import type { ReactNode } from "react";
export const messages = { en: { common: { export: "Export", retry: "Retry" }, chat: { send: "Send" }, editor: { rewrite: "Rewrite" }, workflows: { budget: "Budget" } }, zh: { common: { export: "导出", retry: "重试" }, chat: { send: "发送" }, editor: { rewrite: "改写" }, workflows: { budget: "预算" } } } as const;
type Locale = keyof typeof messages;
const I18nContext = createContext<Locale>("en");
export function I18nProvider({ locale = "en", children }: { locale?: Locale; children: ReactNode }) { return <I18nContext.Provider value={locale}>{children}</I18nContext.Provider>; }
export function useT() { const locale = useContext(I18nContext); return (key: `${keyof typeof messages.en}.${string}`) => { const [feature, item] = key.split(".") as [keyof typeof messages.en, string]; return (messages[locale][feature] as Record<string, string>)[item] ?? key; }; }
