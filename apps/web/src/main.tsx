import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./app/App";
import { registerServiceWorker } from "./lib/pwa/register";

registerServiceWorker();
createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
