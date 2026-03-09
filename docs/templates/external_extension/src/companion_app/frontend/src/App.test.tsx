import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

interface RecordedCall {
  path: string;
  method: string;
  body: unknown;
}

const DEFAULT_CONFIG = {
  mode: {
    role_id: "general_assistant",
    relationship_style: "platonic",
    custom_style: null,
  },
  memory: {
    session_memory_enabled: true,
    profile_memory_enabled: true,
    episodic_memory_enabled: false,
  },
  voice: {
    enabled: false,
    silence_delay_sec: 1.5,
    silence_delay_min_sec: 0.2,
    silence_delay_max_sec: 10,
    adaptive_cadence_enabled: false,
    adaptive_cadence_min_sec: 0.4,
    adaptive_cadence_max_sec: 4,
  },
};

function parseBody(body: BodyInit | null | undefined): unknown {
  if (typeof body !== "string") {
    return undefined;
  }
  try {
    return JSON.parse(body) as unknown;
  } catch {
    return body;
  }
}

function jsonResponse(payload: unknown, status: number = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : null;
}

function installFetchMock(): RecordedCall[] {
  const calls: RecordedCall[] = [];
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const requestUrl =
      typeof input === "string"
        ? input
        : input instanceof URL
          ? input.toString()
          : input.url;
    const url = new URL(requestUrl, "http://localhost");
    const method = String(init?.method ?? "GET").toUpperCase();
    const body = parseBody(init?.body);

    calls.push({ path: url.pathname, method, body });

    if (method === "GET" && url.pathname === "/api/status") {
      return jsonResponse({
        ok: true,
        model_available: true,
        stt_available: true,
        tts_available: false,
        text_only_degraded: false,
        voice_state: "stop",
        voice_silence_delay_sec: 1.5,
        active_sessions: 1,
      });
    }

    if (method === "GET" && url.pathname === "/api/config") {
      const sessionId = url.searchParams.get("session_id") ?? "local-session-1";
      return jsonResponse({
        ok: true,
        session_id: sessionId,
        config: DEFAULT_CONFIG,
      });
    }

    if (method === "PATCH" && url.pathname === "/api/config") {
      const parsed = asRecord(body) ?? {};
      return jsonResponse({
        ok: true,
        session_id: String(parsed.session_id ?? "local-session-1"),
        scope: String(parsed.scope ?? "next_turn"),
        config: DEFAULT_CONFIG,
      });
    }

    if (method === "GET" && url.pathname === "/api/history") {
      const sessionId = url.searchParams.get("session_id") ?? "local-session-1";
      return jsonResponse({
        ok: true,
        session_id: sessionId,
        history: [],
      });
    }

    if (method === "GET" && url.pathname === "/api/voice/state") {
      return jsonResponse({ ok: true, state: "stop", silence_delay_sec: 1.5 });
    }

    if (method === "POST" && url.pathname === "/api/voice/control") {
      const parsed = asRecord(body) ?? {};
      return jsonResponse({
        ok: true,
        state: String(parsed.command ?? "stop"),
        error_code: null,
        error_message: "",
      });
    }

    if (method === "POST" && url.pathname === "/api/chat") {
      const parsed = asRecord(body) ?? {};
      return jsonResponse({
        ok: true,
        session_id: String(parsed.session_id ?? "local-session-1"),
        turn_id: "turn.000001",
        message: "mock companion reply",
        model: "mock-model",
        latency_ms: 5,
        text_only_degraded: false,
      });
    }

    if (method === "POST" && url.pathname === "/api/session/clear-memory") {
      const parsed = asRecord(body) ?? {};
      return jsonResponse({
        ok: true,
        session_id: String(parsed.session_id ?? "local-session-1"),
        deleted_records: 0,
        deleted_episodic_records: 0,
      });
    }

    return jsonResponse({ detail: "mock route not configured" }, 404);
  });

  vi.stubGlobal("fetch", fetchMock);
  return calls;
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("Companion App", () => {
  it("Layer: contract. shows voice controls and sends explicit voice commands.", async () => {
    const calls = installFetchMock();
    const user = userEvent.setup();

    render(<App />);

    await screen.findByText(/synced with host/i);
    await user.click(screen.getByRole("button", { name: /start/i }));

    await waitFor(() => {
      expect(
        calls.some((call) => {
          const payload = asRecord(call.body);
          return call.path === "/api/voice/control" && payload?.command === "start";
        }),
      ).toBe(true);
    });
  });

  it("Layer: contract. preserves explicit text submit semantics even after voice control changes.", async () => {
    const calls = installFetchMock();
    const user = userEvent.setup();

    render(<App />);

    await screen.findByText(/synced with host/i);

    const slider = screen.getByRole("slider");
    fireEvent.change(slider, { target: { value: "3.2" } });
    await user.click(screen.getByRole("button", { name: /start/i }));

    const composer = screen.getByPlaceholderText("Type your message and press Send");
    await user.type(composer, "send explicitly");
    await user.click(screen.getByRole("button", { name: /^send$/i }));

    await waitFor(() => {
      expect(calls.some((call) => call.path === "/api/chat")).toBe(true);
    });

    const chatCall = [...calls].reverse().find((call) => call.path === "/api/chat");
    const chatPayload = asRecord(chatCall?.body);
    expect(chatPayload?.message).toBe("send explicitly");
    expect(chatPayload).not.toHaveProperty("silence_delay_sec");
  });

  it("Layer: contract. swaps avatar and chat panel positions on user request.", async () => {
    installFetchMock();
    const user = userEvent.setup();

    render(<App />);

    await screen.findByText(/synced with host/i);
    const initialOrder = screen.getAllByRole("heading", { level: 2 }).map((item) => item.textContent);
    expect(initialOrder).toEqual(["Presence", "Chat"]);

    await user.click(screen.getByRole("button", { name: /swap avatar\/chat/i }));
    const swappedOrder = screen.getAllByRole("heading", { level: 2 }).map((item) => item.textContent);
    expect(swappedOrder).toEqual(["Chat", "Presence"]);
  });

  it("Layer: contract. supports keyboard traversal from settings rail to chat composer controls.", async () => {
    installFetchMock();
    const user = userEvent.setup();

    render(<App />);

    await screen.findByText(/synced with host/i);

    const sessionInput = screen.getByLabelText("Session");
    const chatInput = screen.getByPlaceholderText("Type your message and press Send");

    await user.tab();
    expect(document.activeElement).toBe(sessionInput);

    let reachedComposer = false;
    for (let index = 0; index < 32; index += 1) {
      await user.tab();
      if (document.activeElement === chatInput) {
        reachedComposer = true;
        break;
      }
    }

    expect(reachedComposer).toBe(true);
  });

  it("Layer: contract. keeps presence panel rendered when avatar asset fails to load.", async () => {
    installFetchMock();
    const user = userEvent.setup();

    render(<App />);

    await screen.findByText(/synced with host/i);
    await user.type(screen.getByLabelText("Avatar Asset (optional)"), "https://example.test/avatar.png");

    const avatarImage = await screen.findByAltText("Companion avatar");
    fireEvent.error(avatarImage);

    await waitFor(() => {
      expect(screen.queryByAltText("Companion avatar")).toBeNull();
    });
    expect(screen.getByText("Companion remains present even when decorative assets are missing.")).toBeTruthy();
  });
});
