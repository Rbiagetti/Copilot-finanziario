const PING_INTERVAL_MS = 14 * 60 * 1000;
const HEALTH_URL = `${import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1"}/health`;

let intervalId: ReturnType<typeof setInterval> | null = null;

export function startKeepAlive() {
  if (intervalId) return;
  fetch(HEALTH_URL).catch(() => {});
  intervalId = setInterval(() => {
    fetch(HEALTH_URL).catch(() => {});
  }, PING_INTERVAL_MS);
}

export function stopKeepAlive() {
  if (intervalId) {
    clearInterval(intervalId);
    intervalId = null;
  }
}
