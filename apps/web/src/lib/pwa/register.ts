const OFFLINE_ID = "proseforge-offline-status";

function setOfflineStatus(offline: boolean): void {
  document.documentElement.dataset.offline = offline ? "true" : "false";
  let status = document.getElementById(OFFLINE_ID);
  if (!status) {
    status = document.createElement("div");
    status.id = OFFLINE_ID;
    status.className = "offline-status";
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    document.body.append(status);
  }
  status.textContent = offline ? "Offline — drafts remain available; generation and export are read-only." : "";
  status.hidden = !offline;
}

export function registerServiceWorker(): void {
  if (typeof window === "undefined") return;
  setOfflineStatus(!navigator.onLine);
  window.addEventListener("offline", () => setOfflineStatus(true));
  window.addEventListener("online", () => setOfflineStatus(false));
  if ("serviceWorker" in navigator && import.meta.env.PROD) {
    void navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => setOfflineStatus(!navigator.onLine));
  }
}
