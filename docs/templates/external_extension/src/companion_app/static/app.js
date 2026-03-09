const els = {
  sessionId: document.querySelector("#session-id"),
  modeRole: document.querySelector("#mode-role"),
  modeStyle: document.querySelector("#mode-style"),
  toggleSessionMemory: document.querySelector("#toggle-session-memory"),
  toggleProfileMemory: document.querySelector("#toggle-profile-memory"),
  voiceDelay: document.querySelector("#voice-delay"),
  voiceState: document.querySelector("#voice-state"),
  ttsText: document.querySelector("#tts-text"),
  ttsAudio: document.querySelector("#tts-audio"),
  ttsStatus: document.querySelector("#tts-status"),
  chatLog: document.querySelector("#chat-log"),
  chatForm: document.querySelector("#chat-form"),
  chatInput: document.querySelector("#chat-input"),
  status: document.querySelector("#status"),
};

let lastAssistantMessage = "";
let ttsObjectUrl = "";

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
  const voiceStatus = payload.text_only_degraded
    ? "text-only degraded (STT unavailable)"
    : "voice path available";
  const ttsStatus = payload.tts_available ? "TTS available" : "TTS unavailable";
  els.status.textContent = `Host status: ${voiceStatus} | ${ttsStatus}`;
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
  lastAssistantMessage = payload.message || "";
  addMessage("assistant", lastAssistantMessage);
  if (lastAssistantMessage) {
    els.ttsText.value = lastAssistantMessage;
  }
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

function releaseTtsObjectUrl() {
  if (!ttsObjectUrl) return;
  URL.revokeObjectURL(ttsObjectUrl);
  ttsObjectUrl = "";
}

function decodeBase64ToBytes(payload) {
  const encoded = String(payload || "");
  const binary = atob(encoded);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

function pcmS16leToWavBlob(audioB64, sampleRate, channels) {
  const pcmBytes = decodeBase64ToBytes(audioB64);
  const byteRate = sampleRate * channels * 2;
  const blockAlign = channels * 2;
  const wavBuffer = new ArrayBuffer(44 + pcmBytes.length);
  const view = new DataView(wavBuffer);
  const out = new Uint8Array(wavBuffer);

  const writeAscii = (offset, value) => {
    for (let index = 0; index < value.length; index += 1) {
      view.setUint8(offset + index, value.charCodeAt(index));
    }
  };

  writeAscii(0, "RIFF");
  view.setUint32(4, 36 + pcmBytes.length, true);
  writeAscii(8, "WAVE");
  writeAscii(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, channels, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, byteRate, true);
  view.setUint16(32, blockAlign, true);
  view.setUint16(34, 16, true);
  writeAscii(36, "data");
  view.setUint32(40, pcmBytes.length, true);
  out.set(pcmBytes, 44);

  return new Blob([out], { type: "audio/wav" });
}

async function synthesize(text) {
  return request("/api/voice/synthesize", {
    method: "POST",
    body: JSON.stringify({ text }),
  });
}

async function synthesizeAndPlay(text) {
  const trimmed = String(text || "").trim();
  if (!trimmed) {
    els.ttsStatus.textContent = "TTS: enter text to synthesize.";
    return;
  }
  const payload = await synthesize(trimmed);
  if (!payload.ok || !payload.audio_b64) {
    const errorCode = payload.error_code || "tts_unavailable";
    const errorMessage = payload.error_message || "No audio generated.";
    els.ttsStatus.textContent = `TTS: ${errorCode} (${errorMessage})`;
    return;
  }
  if (payload.format !== "pcm_s16le") {
    els.ttsStatus.textContent = `TTS: unsupported format ${payload.format}`;
    return;
  }

  const wavBlob = pcmS16leToWavBlob(
    payload.audio_b64,
    Number(payload.sample_rate || 22050),
    Number(payload.channels || 1),
  );
  releaseTtsObjectUrl();
  ttsObjectUrl = URL.createObjectURL(wavBlob);
  els.ttsAudio.src = ttsObjectUrl;

  try {
    await els.ttsAudio.play();
    els.ttsStatus.textContent = `TTS: playing voice ${payload.voice_id || "unknown"}`;
  } catch (_error) {
    els.ttsStatus.textContent = "TTS: audio generated (click Play to start).";
  }
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

document.querySelector("#voice-start").addEventListener("click", async () => {
  try {
    await voiceControl("start");
  } catch (error) {
    els.status.textContent = `Voice error: ${error.message}`;
  }
});

document.querySelector("#voice-submit").addEventListener("click", async () => {
  try {
    await voiceControl("submit");
  } catch (error) {
    els.status.textContent = `Voice error: ${error.message}`;
  }
});

document.querySelector("#voice-stop").addEventListener("click", async () => {
  try {
    await voiceControl("stop");
  } catch (error) {
    els.status.textContent = `Voice error: ${error.message}`;
  }
});

document.querySelector("#tts-speak").addEventListener("click", async () => {
  try {
    await synthesizeAndPlay(els.ttsText.value);
  } catch (error) {
    els.ttsStatus.textContent = `TTS error: ${error.message}`;
  }
});

document.querySelector("#tts-speak-last").addEventListener("click", async () => {
  try {
    await synthesizeAndPlay(lastAssistantMessage);
  } catch (error) {
    els.ttsStatus.textContent = `TTS error: ${error.message}`;
  }
});

window.addEventListener("beforeunload", () => {
  releaseTtsObjectUrl();
});

Promise.all([refreshStatus(), refreshConfig(), refreshHistory()])
  .catch((error) => {
    els.status.textContent = `Startup error: ${error.message}`;
  });
