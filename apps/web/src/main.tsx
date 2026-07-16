import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { AppQueryProvider } from "./app/query";
import { LanguageProvider } from "./lib/i18n";
import { App } from "./workspace";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <LanguageProvider>
      <AppQueryProvider>
        <App />
      </AppQueryProvider>
    </LanguageProvider>
  </StrictMode>,
);
