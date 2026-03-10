import type {
  ChatRequest,
  ChatResponse,
  ClearSessionMemoryResponse,
  ConfigResponse,
  ConfigUpdateResponse,
  HistoryResponse,
  ModelCatalogResponse,
  StatusResponse,
  UpdateConfigRequest,
  VoiceCommand,
  VoiceControlResponse,
  VoiceStateResponse,
} from "../types";

export class CompanionApiClient {
  constructor(private readonly basePath: string = "/api") {}

  async status(): Promise<StatusResponse> {
    return this.request<StatusResponse>("/status");
  }

  async getConfig(sessionId: string): Promise<ConfigResponse> {
    const params = new URLSearchParams({ session_id: sessionId });
    return this.request<ConfigResponse>(`/config?${params.toString()}`);
  }

  async updateConfig(request: UpdateConfigRequest): Promise<ConfigUpdateResponse> {
    return this.request<ConfigUpdateResponse>("/config", {
      method: "PATCH",
      body: JSON.stringify(request),
    });
  }

  async history(sessionId: string, limit: number = 40): Promise<HistoryResponse> {
    const params = new URLSearchParams({
      session_id: sessionId,
      limit: String(Math.max(1, Math.floor(limit))),
    });
    return this.request<HistoryResponse>(`/history?${params.toString()}`);
  }

  async models(provider: string): Promise<ModelCatalogResponse> {
    const params = new URLSearchParams({ provider: String(provider || "ollama") });
    return this.request<ModelCatalogResponse>(`/models?${params.toString()}`);
  }

  async chat(request: ChatRequest): Promise<ChatResponse> {
    return this.request<ChatResponse>("/chat", {
      method: "POST",
      body: JSON.stringify(request),
    });
  }

  async clearSessionMemory(sessionId: string): Promise<ClearSessionMemoryResponse> {
    return this.request<ClearSessionMemoryResponse>("/session/clear-memory", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId }),
    });
  }

  async voiceState(): Promise<VoiceStateResponse> {
    return this.request<VoiceStateResponse>("/voice/state");
  }

  async voiceControl(command: VoiceCommand, silenceDelaySec: number): Promise<VoiceControlResponse> {
    return this.request<VoiceControlResponse>("/voice/control", {
      method: "POST",
      body: JSON.stringify({
        command,
        silence_delay_sec: silenceDelaySec,
      }),
    });
  }

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const headers = new Headers(init?.headers || {});
    if (init?.body && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }

    const response = await fetch(`${this.basePath}${path}`, {
      ...init,
      headers,
    });

    const textPayload = await response.text();
    const parsedPayload = textPayload ? tryParseJson(textPayload) : null;

    if (!response.ok) {
      const message = extractErrorMessage(parsedPayload, textPayload, response.statusText);
      throw new Error(message);
    }

    return (parsedPayload ?? ({} as T)) as T;
  }
}

function tryParseJson(payload: string): unknown {
  try {
    return JSON.parse(payload);
  } catch {
    return payload;
  }
}

function extractErrorMessage(payload: unknown, raw: string, fallback: string): string {
  if (payload && typeof payload === "object") {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }
    if (detail && typeof detail === "object") {
      const detailMessage = (detail as { message?: unknown }).message;
      if (typeof detailMessage === "string" && detailMessage.trim()) {
        return detailMessage;
      }
    }
    const message = (payload as { message?: unknown }).message;
    if (typeof message === "string" && message.trim()) {
      return message;
    }
  }

  const normalized = String(raw || "").trim();
  return normalized || fallback || "Host request failed.";
}
