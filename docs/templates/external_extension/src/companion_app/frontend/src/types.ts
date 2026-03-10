export type CompanionConfigScope = "profile" | "session" | "next_turn";

export type VoiceCommand = "start" | "stop" | "submit";

export type CompanionProvider = "ollama" | "lmstudio" | "openai_compat";

export interface CompanionModeConfig {
  role_id: string;
  relationship_style: string;
  custom_style?: Record<string, unknown> | null;
}

export interface CompanionMemoryConfig {
  session_memory_enabled: boolean;
  profile_memory_enabled: boolean;
  episodic_memory_enabled: boolean;
}

export interface CompanionVoiceConfig {
  enabled: boolean;
  silence_delay_sec: number;
  silence_delay_min_sec: number;
  silence_delay_max_sec: number;
  adaptive_cadence_enabled: boolean;
  adaptive_cadence_min_sec: number;
  adaptive_cadence_max_sec: number;
}

export interface CompanionConfig {
  mode: CompanionModeConfig;
  memory: CompanionMemoryConfig;
  voice: CompanionVoiceConfig;
}

export interface HistoryRow {
  role: string;
  content: string;
  timestamp_utc?: string;
}

export interface StatusResponse {
  ok: boolean;
  model_available: boolean;
  stt_available: boolean;
  tts_available: boolean;
  text_only_degraded: boolean;
  voice_state: string;
  voice_silence_delay_sec: number;
  active_sessions: number;
}

export interface VoiceStateResponse {
  ok: boolean;
  state: string;
  silence_delay_sec: number;
}

export interface VoiceControlResponse {
  ok: boolean;
  state: string;
  error_code: string | null;
  error_message: string;
}

export interface ConfigResponse {
  ok: boolean;
  session_id: string;
  config: CompanionConfig;
}

export interface ConfigUpdateResponse {
  ok: boolean;
  session_id: string;
  scope: CompanionConfigScope;
  config: CompanionConfig;
}

export interface HistoryResponse {
  ok: boolean;
  session_id: string;
  history: HistoryRow[];
}

export interface ModelCatalogResponse {
  ok: boolean;
  requested_provider: string;
  canonical_provider: string;
  base_url: string;
  models: string[];
  default_model: string;
  degraded?: boolean;
}

export interface ChatResponse {
  ok: boolean;
  session_id: string;
  turn_id: string;
  message: string;
  model: string;
  latency_ms: number;
  text_only_degraded: boolean;
  config?: CompanionConfig;
}

export interface ClearSessionMemoryResponse {
  ok: boolean;
  session_id: string;
  deleted_records: number;
  deleted_episodic_records: number;
}

export interface ChatRequest {
  session_id: string;
  message: string;
  provider?: string;
  model?: string;
}

export interface UpdateConfigRequest {
  session_id: string;
  scope: CompanionConfigScope;
  patch: {
    mode: CompanionModeConfig;
    memory: CompanionMemoryConfig;
    voice: Pick<CompanionVoiceConfig, "silence_delay_sec">;
  };
}
