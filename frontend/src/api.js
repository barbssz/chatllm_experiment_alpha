const API_BASE = window.location.origin;

async function apiFetch(path, { method = "GET", body, signal } = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      "X-Requested-With": "ChatLLM",
    },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const detail = typeof payload.detail === "string"
      ? payload.detail
      : "Confira os campos informados e tente novamente.";
    const error = new Error(detail);
    error.status = response.status;
    throw error;
  }
  return response;
}

async function registerUser(email, password) {
  const response = await apiFetch("/api/auth/register", { method: "POST", body: { email, password } });
  return response.json();
}

async function loginUser(email, password) {
  const response = await apiFetch("/api/auth/login", { method: "POST", body: { email, password } });
  return response.json();
}

async function getCurrentUser() {
  const response = await apiFetch("/api/auth/me");
  return response.json();
}

async function logoutUser() {
  await apiFetch("/api/auth/logout", { method: "POST" });
}

async function sendMessageStream({ message, history, onDelta, signal }) {
  const response = await apiFetch("/api/chat/stream", {
    method: "POST",
    body: { message, history },
    signal,
  });

  if (!response.body) {
    throw new Error("Streaming nao suportado no ambiente atual.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() || "";

    for (const rawEvent of events) {
      const line = rawEvent
        .split("\n")
        .find((part) => part.startsWith("data:"));
      if (!line) continue;

      const payloadText = line.slice(5).trim();
      if (!payloadText) continue;

      let payload;
      try {
        payload = JSON.parse(payloadText);
      } catch {
        continue;
      }

      if (payload.error) {
        throw new Error(payload.error);
      }

      if (payload.delta) {
        onDelta(payload.delta);
      }
    }
  }
}
