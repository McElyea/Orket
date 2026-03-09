import * as Accordion from "@radix-ui/react-accordion";
import * as Switch from "@radix-ui/react-switch";
import {
  AudioLines,
  Brain,
  ChevronDown,
  ChevronsLeftRight,
  Mic,
  MicOff,
  RotateCcw,
  Save,
  SendHorizonal,
  Settings2,
  UserRound,
  Waves,
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { CompanionApiClient } from "./api/client";
import type {
  CompanionConfig,
  CompanionConfigScope,
  HistoryRow,
  StatusResponse,
  VoiceCommand,
  VoiceStateResponse,
} from "./types";
import styles from "./styles/App.module.scss";

type FontPersonality = "girly" | "manly" | "neutral" | "weird" | "elegant" | "playful" | "techno";

type PresenceMood = "neutral" | "warm" | "focused" | "curious";

const ROLE_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "general_assistant", label: "General Assistant" },
  { value: "supportive_listener", label: "Supportive Listener" },
  { value: "researcher", label: "Researcher" },
  { value: "programmer", label: "Programmer" },
  { value: "strategist", label: "Strategist" },
  { value: "tutor", label: "Tutor" },
];

const STYLE_OPTIONS: Array<{ value: string; label: string; disabled?: boolean }> = [
  { value: "platonic", label: "Platonic" },
  { value: "intermediate", label: "Intermediate" },
  { value: "romantic", label: "Romantic" },
  { value: "custom", label: "Custom (host-defined)", disabled: true },
];

const FONT_PERSONALITIES: Array<{ value: FontPersonality; label: string }> = [
  { value: "girly", label: "Girly (Quicksand)" },
  { value: "manly", label: "Manly (IBM Plex Sans)" },
  { value: "neutral", label: "Neutral (Source Sans 3)" },
  { value: "weird", label: "Weird (Space Grotesk)" },
  { value: "elegant", label: "Elegant (Playfair Display)" },
  { value: "playful", label: "Playful (Nunito)" },
  { value: "techno", label: "Techno (Fira Sans)" },
];

const DEFAULT_CONFIG: CompanionConfig = {
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

const DEFAULT_VOICE_STATE: VoiceStateResponse = {
  ok: true,
  state: "stop",
  silence_delay_sec: 1.5,
};

function inferPresenceMood(text: string): PresenceMood {
  const normalized = text.toLowerCase();
  if (!normalized) {
    return "neutral";
  }
  if (normalized.includes("?") || normalized.includes("curious") || normalized.includes("wonder")) {
    return "curious";
  }
  if (normalized.includes("step") || normalized.includes("plan") || normalized.includes("focus")) {
    return "focused";
  }
  if (normalized.includes("glad") || normalized.includes("care") || normalized.includes("with you")) {
    return "warm";
  }
  return "neutral";
}

function humanizeState(raw: string): string {
  const normalized = String(raw || "").trim();
  if (!normalized) {
    return "unknown";
  }
  return normalized.replace(/_/g, " ");
}

function safeDelay(value: number, min: number, max: number): number {
  if (Number.isNaN(value)) {
    return min;
  }
  return Math.min(max, Math.max(min, value));
}

export function App(): JSX.Element {
  const api = useMemo(() => new CompanionApiClient("/api"), []);

  const [sessionInput, setSessionInput] = useState("local-session-1");
  const [sessionId, setSessionId] = useState("local-session-1");
  const [chatDraft, setChatDraft] = useState("");
  const [history, setHistory] = useState<HistoryRow[]>([]);
  const [config, setConfig] = useState<CompanionConfig>(DEFAULT_CONFIG);
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [voiceState, setVoiceState] = useState<VoiceStateResponse>(DEFAULT_VOICE_STATE);
  const [fontPersonality, setFontPersonality] = useState<FontPersonality>("neutral");
  const [avatarUrl, setAvatarUrl] = useState("");
  const [avatarLoadFailed, setAvatarLoadFailed] = useState(false);
  const [panesSwapped, setPanesSwapped] = useState(false);
  const [notice, setNotice] = useState("I am here with you, not at you.");
  const [busy, setBusy] = useState(false);
  const [sending, setSending] = useState(false);

  const latestAssistantText = useMemo(() => {
    for (let index = history.length - 1; index >= 0; index -= 1) {
      if (history[index].role === "assistant") {
        return String(history[index].content || "");
      }
    }
    return "";
  }, [history]);

  const presenceMood = useMemo(() => inferPresenceMood(latestAssistantText), [latestAssistantText]);

  const refreshStatus = useCallback(async (): Promise<void> => {
    const payload = await api.status();
    setStatus(payload);
  }, [api]);

  const refreshVoice = useCallback(async (): Promise<void> => {
    const payload = await api.voiceState();
    setVoiceState(payload);
    setConfig((current) => ({
      ...current,
      voice: {
        ...current.voice,
        silence_delay_sec: safeDelay(
          payload.silence_delay_sec,
          current.voice.silence_delay_min_sec,
          current.voice.silence_delay_max_sec,
        ),
      },
    }));
  }, [api]);

  const refreshConfig = useCallback(async (): Promise<void> => {
    const payload = await api.getConfig(sessionId);
    setConfig(payload.config);
  }, [api, sessionId]);

  const refreshHistory = useCallback(async (): Promise<void> => {
    const payload = await api.history(sessionId, 40);
    setHistory(payload.history || []);
  }, [api, sessionId]);

  const refreshAll = useCallback(async (): Promise<void> => {
    setBusy(true);
    try {
      await Promise.all([refreshStatus(), refreshConfig(), refreshHistory(), refreshVoice()]);
      setNotice(`Session ${sessionId} synced with host.`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to refresh host state.";
      setNotice(`Refresh error: ${message}`);
    } finally {
      setBusy(false);
    }
  }, [refreshConfig, refreshHistory, refreshStatus, refreshVoice, sessionId]);

  useEffect(() => {
    void refreshAll();
    const timer = window.setInterval(() => {
      void refreshStatus();
      void refreshVoice();
    }, 9000);
    return () => window.clearInterval(timer);
  }, [refreshAll, refreshStatus, refreshVoice]);

  const applySettings = useCallback(
    async (scope: CompanionConfigScope): Promise<void> => {
      const payload = await api.updateConfig({
        session_id: sessionId,
        scope,
        patch: {
          mode: {
            role_id: config.mode.role_id,
            relationship_style: config.mode.relationship_style,
            custom_style:
              config.mode.relationship_style === "custom"
                ? config.mode.custom_style ?? {}
                : null,
          },
          memory: {
            session_memory_enabled: config.memory.session_memory_enabled,
            profile_memory_enabled: config.memory.profile_memory_enabled,
            episodic_memory_enabled: config.memory.episodic_memory_enabled,
          },
          voice: {
            silence_delay_sec: safeDelay(
              config.voice.silence_delay_sec,
              config.voice.silence_delay_min_sec,
              config.voice.silence_delay_max_sec,
            ),
          },
        },
      });
      setConfig(payload.config);
      setNotice(
        scope === "profile"
          ? "Saved current settings as profile defaults."
          : "Queued settings for the next turn.",
      );
    },
    [api, config, sessionId],
  );

  const handleChatSubmit = useCallback(
    async (event: FormEvent<HTMLFormElement>): Promise<void> => {
      event.preventDefault();
      const message = chatDraft.trim();
      if (!message || sending) {
        return;
      }
      setSending(true);
      setChatDraft("");
      setHistory((current) => [...current, { role: "user", content: message }]);
      try {
        const payload = await api.chat({ session_id: sessionId, message });
        setHistory((current) => [...current, { role: "assistant", content: payload.message || "" }]);
        if (payload.config) {
          setConfig(payload.config);
        }
        setNotice(
          payload.text_only_degraded
            ? `Text-only mode active. Reply generated in ${payload.latency_ms}ms.`
            : `Reply generated in ${payload.latency_ms}ms.`,
        );
      } catch (error) {
        const detail = error instanceof Error ? error.message : "Chat request failed.";
        setNotice(`Chat error: ${detail}`);
      } finally {
        setSending(false);
      }
    },
    [api, chatDraft, sending, sessionId],
  );

  const runVoiceCommand = useCallback(
    async (command: VoiceCommand): Promise<void> => {
      try {
        const payload = await api.voiceControl(command, config.voice.silence_delay_sec);
        setVoiceState({
          ok: payload.ok,
          state: payload.state,
          silence_delay_sec: config.voice.silence_delay_sec,
        });
        if (payload.error_code) {
          setNotice(`Voice ${command}: ${payload.error_code} ${payload.error_message}`.trim());
          return;
        }
        setNotice(`Voice command '${command}' applied. State is now ${humanizeState(payload.state)}.`);
      } catch (error) {
        const detail = error instanceof Error ? error.message : "Voice request failed.";
        setNotice(`Voice error: ${detail}`);
      }
    },
    [api, config.voice.silence_delay_sec],
  );

  const clearSessionMemory = useCallback(async (): Promise<void> => {
    try {
      const payload = await api.clearSessionMemory(sessionId);
      setHistory([]);
      setNotice(`Cleared session memory (${payload.deleted_records} records).`);
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Session clear failed.";
      setNotice(`Clear memory error: ${detail}`);
    }
  }, [api, sessionId]);

  const sttUnavailable = Boolean(status?.text_only_degraded || (status && !status.stt_available));

  const statusToneClass = sttUnavailable ? styles.statusBadgeDegraded : styles.statusBadgeReady;

  return (
    <div className={styles.appShell} data-font-personality={fontPersonality}>
      <main className={styles.mainGrid}>
        <aside className={styles.leftRail}>
          <div className={styles.railHeader}>
            <p className={styles.railEyebrow}>Companion</p>
            <h1 className={styles.railTitle}>Calm Companion MVP</h1>
            <p className={styles.railSubtitle}>Local web app with host-owned runtime behavior.</p>
          </div>

          <div className={styles.railSection}>
            <label className={styles.fieldLabel} htmlFor="session-id">
              Session
            </label>
            <input
              id="session-id"
              className={styles.textInput}
              value={sessionInput}
              onChange={(event) => setSessionInput(event.target.value)}
            />
            <div className={styles.inlineButtons}>
              <button
                type="button"
                className={styles.secondaryButton}
                onClick={() => {
                  const next = sessionInput.trim() || "local-session-1";
                  setSessionInput(next);
                  setSessionId(next);
                }}
              >
                Load Session
              </button>
              <button type="button" className={styles.ghostButton} onClick={() => void refreshAll()} disabled={busy}>
                {busy ? "Syncing..." : "Refresh"}
              </button>
            </div>
          </div>

          <div className={styles.railSection}>
            <label className={styles.fieldLabel} htmlFor="role-id">
              Role
            </label>
            <select
              id="role-id"
              className={styles.selectInput}
              value={config.mode.role_id}
              onChange={(event) =>
                setConfig((current) => ({
                  ...current,
                  mode: {
                    ...current.mode,
                    role_id: event.target.value,
                  },
                }))
              }
            >
              {ROLE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>

            <label className={styles.fieldLabel} htmlFor="style-id">
              Relationship Style
            </label>
            <select
              id="style-id"
              className={styles.selectInput}
              value={config.mode.relationship_style}
              onChange={(event) =>
                setConfig((current) => ({
                  ...current,
                  mode: {
                    ...current.mode,
                    relationship_style: event.target.value,
                  },
                }))
              }
            >
              {STYLE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value} disabled={Boolean(option.disabled)}>
                  {option.label}
                </option>
              ))}
            </select>

            <label className={styles.fieldLabel} htmlFor="font-personality">
              Font Personality
            </label>
            <select
              id="font-personality"
              className={styles.selectInput}
              value={fontPersonality}
              onChange={(event) => setFontPersonality(event.target.value as FontPersonality)}
            >
              {FONT_PERSONALITIES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className={styles.railSection}>
            <label className={styles.fieldLabel} htmlFor="avatar-url">
              Avatar Asset (optional)
            </label>
            <input
              id="avatar-url"
              className={styles.textInput}
              placeholder="https://..."
              value={avatarUrl}
              onChange={(event) => {
                setAvatarLoadFailed(false);
                setAvatarUrl(event.target.value);
              }}
            />
            <p className={styles.helperText}>Missing assets fall back to a built-in presence shape.</p>
          </div>

          <div className={styles.inlineButtons}>
            <button type="button" className={styles.primaryButton} onClick={() => void applySettings("next_turn")}>
              <Settings2 size={16} aria-hidden="true" />
              Queue Next Turn
            </button>
            <button type="button" className={styles.secondaryButton} onClick={() => void applySettings("profile")}>
              <Save size={16} aria-hidden="true" />
              Save Profile
            </button>
          </div>

          <div className={styles.inlineButtons}>
            <button type="button" className={styles.ghostButton} onClick={() => setPanesSwapped((current) => !current)}>
              <ChevronsLeftRight size={16} aria-hidden="true" />
              Swap Avatar/Chat
            </button>
          </div>
        </aside>

        {panesSwapped ? (
          <ChatPanel
            chatDraft={chatDraft}
            sending={sending}
            sttUnavailable={sttUnavailable}
            history={history}
            onChatDraftChange={setChatDraft}
            onSubmit={handleChatSubmit}
          />
        ) : (
          <PresencePanel
            avatarLoadFailed={avatarLoadFailed}
            avatarUrl={avatarUrl}
            mood={presenceMood}
            sttUnavailable={sttUnavailable}
            voiceState={voiceState.state}
            onAvatarError={() => setAvatarLoadFailed(true)}
          />
        )}

        {panesSwapped ? (
          <PresencePanel
            avatarLoadFailed={avatarLoadFailed}
            avatarUrl={avatarUrl}
            mood={presenceMood}
            sttUnavailable={sttUnavailable}
            voiceState={voiceState.state}
            onAvatarError={() => setAvatarLoadFailed(true)}
          />
        ) : (
          <ChatPanel
            chatDraft={chatDraft}
            sending={sending}
            sttUnavailable={sttUnavailable}
            history={history}
            onChatDraftChange={setChatDraft}
            onSubmit={handleChatSubmit}
          />
        )}
      </main>

      <section className={styles.controlPanel}>
        <div className={styles.noticeBar}>{notice}</div>
        <Accordion.Root className={styles.accordionRoot} type="multiple" defaultValue={["voice", "status"]}>
          <Accordion.Item className={styles.accordionItem} value="voice">
            <Accordion.Header>
              <Accordion.Trigger className={styles.accordionTrigger}>
                <span className={styles.triggerLabel}>
                  <AudioLines size={16} aria-hidden="true" />
                  Voice Controls
                </span>
                <ChevronDown className={styles.triggerIcon} size={16} aria-hidden="true" />
              </Accordion.Trigger>
            </Accordion.Header>
            <Accordion.Content className={styles.accordionContent}>
              <div className={styles.accordionInner}>
                <div className={styles.controlRow}>
                  <span className={styles.controlTitle}>Silence Delay</span>
                  <span className={styles.rangeValue}>{config.voice.silence_delay_sec.toFixed(1)}s</span>
                </div>
                <input
                  className={styles.rangeInput}
                  type="range"
                  min={config.voice.silence_delay_min_sec}
                  max={config.voice.silence_delay_max_sec}
                  step={0.1}
                  value={config.voice.silence_delay_sec}
                  onChange={(event) =>
                    setConfig((current) => ({
                      ...current,
                      voice: {
                        ...current.voice,
                        silence_delay_sec: Number(event.target.value),
                      },
                    }))
                  }
                />
                <p className={styles.helperText}>Text submission always remains explicit and unaffected by voice timing.</p>

                <div className={styles.inlineButtons}>
                  <button type="button" className={styles.secondaryButton} onClick={() => void runVoiceCommand("start")}>
                    <Mic size={16} aria-hidden="true" />
                    Start
                  </button>
                  <button type="button" className={styles.secondaryButton} onClick={() => void runVoiceCommand("submit")}>
                    <SendHorizonal size={16} aria-hidden="true" />
                    Submit
                  </button>
                  <button type="button" className={styles.secondaryButton} onClick={() => void runVoiceCommand("stop")}>
                    <MicOff size={16} aria-hidden="true" />
                    Stop
                  </button>
                </div>
                <p className={styles.helperText}>Current voice state: {humanizeState(voiceState.state)}</p>
              </div>
            </Accordion.Content>
          </Accordion.Item>

          <Accordion.Item className={styles.accordionItem} value="memory">
            <Accordion.Header>
              <Accordion.Trigger className={styles.accordionTrigger}>
                <span className={styles.triggerLabel}>
                  <Brain size={16} aria-hidden="true" />
                  Memory Controls
                </span>
                <ChevronDown className={styles.triggerIcon} size={16} aria-hidden="true" />
              </Accordion.Trigger>
            </Accordion.Header>
            <Accordion.Content className={styles.accordionContent}>
              <div className={styles.accordionInner}>
                <ToggleRow
                  label="Session memory"
                  hint="Turn memory in this session on or off."
                  checked={config.memory.session_memory_enabled}
                  onCheckedChange={(next) =>
                    setConfig((current) => ({
                      ...current,
                      memory: { ...current.memory, session_memory_enabled: next },
                    }))
                  }
                />
                <ToggleRow
                  label="Profile memory"
                  hint="Persist preferences as profile defaults."
                  checked={config.memory.profile_memory_enabled}
                  onCheckedChange={(next) =>
                    setConfig((current) => ({
                      ...current,
                      memory: { ...current.memory, profile_memory_enabled: next },
                    }))
                  }
                />
                <div className={styles.inlineButtons}>
                  <button type="button" className={styles.secondaryButton} onClick={() => void clearSessionMemory()}>
                    <RotateCcw size={16} aria-hidden="true" />
                    Clear Session Memory
                  </button>
                </div>
              </div>
            </Accordion.Content>
          </Accordion.Item>

          <Accordion.Item className={styles.accordionItem} value="status">
            <Accordion.Header>
              <Accordion.Trigger className={styles.accordionTrigger}>
                <span className={styles.triggerLabel}>
                  <Waves size={16} aria-hidden="true" />
                  Status
                </span>
                <ChevronDown className={styles.triggerIcon} size={16} aria-hidden="true" />
              </Accordion.Trigger>
            </Accordion.Header>
            <Accordion.Content className={styles.accordionContent}>
              <div className={styles.accordionInner}>
                <div className={styles.statusGrid}>
                  <div className={styles.statusItem}>
                    <span className={styles.statusLabel}>STT</span>
                    <span className={statusToneClass}>{status?.stt_available ? "available" : "unavailable"}</span>
                  </div>
                  <div className={styles.statusItem}>
                    <span className={styles.statusLabel}>Voice State</span>
                    <span className={styles.statusValue}>{humanizeState(voiceState.state)}</span>
                  </div>
                  <div className={styles.statusItem}>
                    <span className={styles.statusLabel}>Model Path</span>
                    <span className={styles.statusValue}>{status?.model_available ? "ready" : "degraded"}</span>
                  </div>
                  <div className={styles.statusItem}>
                    <span className={styles.statusLabel}>Active Sessions</span>
                    <span className={styles.statusValue}>{status?.active_sessions ?? 0}</span>
                  </div>
                </div>
                <p className={styles.helperText}>
                  {sttUnavailable
                    ? "STT is unavailable, so Companion stays in explicit text mode."
                    : "STT is available. Voice remains optional and user-controlled."}
                </p>
              </div>
            </Accordion.Content>
          </Accordion.Item>
        </Accordion.Root>
      </section>
    </div>
  );
}

interface ChatPanelProps {
  history: HistoryRow[];
  chatDraft: string;
  sending: boolean;
  sttUnavailable: boolean;
  onChatDraftChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}

function ChatPanel({
  history,
  chatDraft,
  sending,
  sttUnavailable,
  onChatDraftChange,
  onSubmit,
}: ChatPanelProps): JSX.Element {
  return (
    <section className={styles.panelSurface}>
      <header className={styles.panelHeader}>
        <h2 className={styles.panelTitle}>Chat</h2>
        <span className={sttUnavailable ? styles.statusBadgeDegraded : styles.statusBadgeReady}>
          {sttUnavailable ? "Text-only" : "Voice optional"}
        </span>
      </header>

      <div className={styles.messageList}>
        {history.length === 0 ? <p className={styles.emptyState}>Start with a message whenever you are ready.</p> : null}
        {history.map((item, index) => {
          const isUser = item.role === "user";
          return (
            <article
              key={`${item.role}-${index}-${item.timestamp_utc || ""}`}
              className={`${styles.messageBubble} ${isUser ? styles.messageUser : styles.messageAssistant}`}
            >
              <span className={styles.roleTag}>{isUser ? "You" : "Companion"}</span>
              <p className={styles.messageText}>{item.content}</p>
            </article>
          );
        })}
      </div>

      <form className={styles.chatComposer} onSubmit={onSubmit}>
        <textarea
          className={styles.chatInput}
          rows={3}
          placeholder="Type your message and press Send"
          value={chatDraft}
          onChange={(event) => onChatDraftChange(event.target.value)}
        />
        <button type="submit" className={styles.primaryButton} disabled={sending || !chatDraft.trim()}>
          <SendHorizonal size={16} aria-hidden="true" />
          {sending ? "Sending..." : "Send"}
        </button>
      </form>
    </section>
  );
}

interface PresencePanelProps {
  avatarUrl: string;
  avatarLoadFailed: boolean;
  mood: PresenceMood;
  voiceState: string;
  sttUnavailable: boolean;
  onAvatarError: () => void;
}

function PresencePanel({
  avatarUrl,
  avatarLoadFailed,
  mood,
  voiceState,
  sttUnavailable,
  onAvatarError,
}: PresencePanelProps): JSX.Element {
  const hasAvatar = avatarUrl.trim().length > 0 && !avatarLoadFailed;

  return (
    <section className={styles.panelSurface}>
      <header className={styles.panelHeader}>
        <h2 className={styles.panelTitle}>Presence</h2>
        <span className={sttUnavailable ? styles.statusBadgeDegraded : styles.statusBadgeReady}>
          {sttUnavailable ? "STT unavailable" : "STT ready"}
        </span>
      </header>

      <div className={styles.presenceStage}>
        <div className={`${styles.avatarFrame} ${voiceState === "start" ? styles.avatarListening : ""}`}>
          {hasAvatar ? (
            <img
              alt="Companion avatar"
              className={styles.avatarImage}
              src={avatarUrl}
              onError={onAvatarError}
            />
          ) : (
            <div className={styles.avatarFallback}>
              <UserRound size={58} aria-hidden="true" />
            </div>
          )}
        </div>

        <div className={styles.moodChip}>
          <span className={styles.statusLabel}>Mood</span>
          <span className={styles.statusValue}>{mood}</span>
        </div>

        <p className={styles.helperText}>
          Companion remains present even when decorative assets are missing.
        </p>
      </div>
    </section>
  );
}

interface ToggleRowProps {
  label: string;
  hint: string;
  checked: boolean;
  onCheckedChange: (next: boolean) => void;
}

function ToggleRow({ label, hint, checked, onCheckedChange }: ToggleRowProps): JSX.Element {
  return (
    <div className={styles.toggleRow}>
      <div>
        <div className={styles.controlTitle}>{label}</div>
        <div className={styles.helperText}>{hint}</div>
      </div>
      <Switch.Root className={styles.switchRoot} checked={checked} onCheckedChange={onCheckedChange}>
        <Switch.Thumb className={styles.switchThumb} />
      </Switch.Root>
    </div>
  );
}
