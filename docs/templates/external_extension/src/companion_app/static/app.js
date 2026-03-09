const els = {
  sessionId: document.querySelector("#session-id"),
  modeRole: document.querySelector("#mode-role"),
  modeStyle: document.querySelector("#mode-style"),
  toggleSessionMemory: document.querySelector("#toggle-session-memory"),
  toggleProfileMemory: document.querySelector("#toggle-profile-memory"),
  voiceDelay: document.querySelector("#voice-delay"),
  voiceState: document.querySelector("#voice-state"),
  chatLog: document.querySelector("#chat-log"),
  chatForm: document.querySelector("#chat-form"),
  chatInput: document.querySelector("#chat-input"),
  status: document.querySelector("#status"),
};

function sessionId() {
  return (els.sessionId.value || "").trim() || "local-session-1";
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload?.detail?.message || payload?.detail || response.statusText);
  }
  return payload;
}

function addMessage(role, content) {
  const item = document.createElement("article");
  item.className = `msg ${role}`;
  item.innerHTML = `<span class="role">${role}</span>${content}`;
  els.chatLog.appendChild(item);
  els.chatLog.scrollTop = els.chatLog.scrollHeight;
}

async function refreshStatus() {
  const payload = await request("/api/status");
  els.status.textContent = payload.text_only_degraded
    ? "Host status: text-only degraded (STT unavailable)"
    : "Host status: voice path available";
}

async function refreshConfig() {
  const payload = await request(`/api/config?session_id=${encodeURIComponent(sessionId())}`);
  const config = payload.config || {};
  const mode = config.mode || {};
  const memory = config.memory || {};
  const voice = config.voice || {};
  if (mode.role_id) els.modeRole.value = mode.role_id;
  if (mode.relationship_style) els.modeStyle.value = mode.relationship_style;
  els.toggleSessionMemory.checked = Boolean(memory.session_memory_enabled);
  els.toggleProfileMemory.checked = Boolean(memory.profile_memory_enabled);
  if (typeof voice.silence_delay_sec === "number") {
    els.voiceDelay.value = String(voice.silence_delay_sec);
  }
}

async function refreshHistory() {
  const payload = await request(`/api/history?session_id=${encodeURIComponent(sessionId())}&limit=30`);
  els.chatLog.replaceChildren();
  for (const row of payload.history || []) {
    addMessage(row.role || "assistant", row.content || "");
  }
}

async function applyNextTurnConfig() {
  const patch = {
    mode: {
      role_id: els.modeRole.value,
      relationship_style: els.modeStyle.value,
    },
    memory: {
      session_memory_enabled: els.toggleSessionMemory.checked,
      profile_memory_enabled: els.toggleProfileMemory.checked,
    },
    voice: {
      silence_delay_sec: Number(els.voiceDelay.value || 2.0),
    },
  };
  await request("/api/config", {
    method: "PATCH",
    body: JSON.stringify({
      session_id: sessionId(),
      scope: "next_turn",
      patch,
    }),
  });
  els.status.textContent = "Queued mode/memory/voice changes for next turn.";
}

async function clearSessionMemory() {
  await request("/api/session/clear-memory", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId() }),
  });
  await refreshHistory();
  els.status.textContent = "Session memory cleared.";
}

async function sendChat(message) {
  addMessage("user", message);
  const payload = await request("/api/chat", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId(), message }),
  });
  addMessage("assistant", payload.message || "");
  els.status.textContent = `Model: ${payload.model || "unknown"} | latency: ${payload.latency_ms || 0}ms`;
}

async function voiceControl(command) {
  const payload = await request("/api/voice/control", {
    method: "POST",
    body: JSON.stringify({
      command,
      silence_delay_sec: Number(els.voiceDelay.value || 2.0),
    }),
  });
  els.voiceState.textContent = `Voice state: ${payload.state}`;
}

els.chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = (els.chatInput.value || "").trim();
  if (!message) return;
  els.chatInput.value = "";
  try {
    await sendChat(message);
  } catch (error) {
    els.status.textContent = `Chat error: ${error.message}`;
  }
});

document.querySelector("#apply-next-turn").addEventListener("click", async () => {
  try {
    await applyNextTurnConfig();
  } catch (error) {
    els.status.textContent = `Config error: ${error.message}`;
  }
});

document.querySelector("#clear-session").addEventListener("click", async () => {
  try {
    await clearSessionMemory();
  } catch (error) {
    els.status.textContent = `Clear error: ${error.message}`;
  }
});

document.querySelector("#refresh-history").addEventListener("click", async () => {
  try {
    await refreshHistory();
  } catch (error) {
    els.status.textContent = `History error: ${error.message}`;
  }
});

document.querySelector("#refresh-status").addEventListener("click", async () => {
  try {
    await refreshStatus();
  } catch (error) {
    els.status.textContent = `Status error: ${error.message}`;
  }
});

document.querySelector("#voice-start").addEventListener("click", () => voiceControl("start"));
document.querySelector("#voice-submit").addEventListener("click", () => voiceControl("submit"));
document.querySelector("#voice-stop").addEventListener("click", () => voiceControl("stop"));

Promise.all([refreshStatus(), refreshConfig(), refreshHistory()])
  .catch((error) => {
    els.status.textContent = `Startup error: ${error.message}`;
  });
