import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./app/App";
import { registerServiceWorker } from "./lib/pwa/register";

document.documentElement.dataset.theme = window.localStorage.getItem("proseforge.theme") === "rubbing" ? "rubbing" : "paper";
registerServiceWorker();
createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
