// Shared shapes mirroring the backend WebSocket payloads (cahier §13).

export type GameStateName =
  | "LOBBY"
  | "BUZZER_OPEN"
  | "BUZZED"
  | "QUESTION_ACTIVE"
  | "REVEAL"
  | "SCOREBOARD"
  | "GAME_END";

export type GameMode = "buzzer" | "qcm" | "blindtest";

// Host editor draft (carries the correct answer — host only).
export interface QcmRoundDraft {
  question: string;
  choices: string[]; // length 4
  correct: number; // 0..3
  time_limit: number;
  points: number;
  bonus?: boolean; // ×2 points
  image?: string | null; // optional prompt image URL (/media/...)
}

export interface QcmQuestion {
  index: number;
  total: number;
  question: string;
  choices: string[];
  time_limit: number;
  ends_at: number;
  choices_at?: number; // server ms the choices unlock (after the reading window)
  server_now?: number; // server clock at emission (clock-skew estimate)
  points: number;
  bonus?: boolean; // ×2 points
  correct?: number; // host only, presented index
  image?: string | null; // optional prompt image URL (/media/...)
}

// Buzzer round draft (used by the host editor and pack editor).
export interface BuzzerRowDraft {
  question: string;
  answer: string;
  points: number;
  bonus?: boolean; // ×2 points
  image?: string | null;
}

// A saved question pack (Phase 4). `items` are mode-specific drafts.
export type PackMode = "buzzer" | "qcm" | "blindtest";

export interface Pack {
  id: string;
  name: string;
  description: string;
  tags: string[];
  mode: PackMode;
  items: unknown[];
  created_at: string;
  updated_at: string;
}

export interface PackSummary {
  id: string;
  name: string;
  mode: PackMode;
  count: number;
  tags: string[];
  updated_at: string;
  builtin?: boolean; // read-only starter pack shipped with the app
}

export interface QcmReveal {
  correct: number;
  distribution: number[]; // length 4, presented order
  deltas: Record<string, number>;
}

export interface ScoreboardRow {
  id: string;
  pseudo: string;
  score: number;
  rank: number;
  delta: number; // >0 = moved up
}

export interface PodiumEntry {
  id: string;
  pseudo: string;
  score: number;
  rank: number;
}

export interface QcmState {
  mode: GameMode;
  state: GameStateName;
  index: number;
  total: number;
  question: QcmQuestion | null;
  progress: { answered: number; total: number };
  reveal: QcmReveal | null;
  scoreboard: ScoreboardRow[];
  gameEnd: { podium: PodiumEntry[] } | null;
  myChoice: number | null; // this player's locked answer
  clockOffset: number; // server_now - Date.now(), estimated when the question started
}

export const EMPTY_QCM: QcmState = {
  mode: "buzzer",
  state: "LOBBY",
  index: -1,
  total: 0,
  question: null,
  progress: { answered: 0, total: 0 },
  reveal: null,
  scoreboard: [],
  gameEnd: null,
  myChoice: null,
  clockOffset: 0,
};

export interface BlindtestTrackDraft {
  spotify_track_id: string;
  uri: string;
  title: string;
  artist: string;
  cover_url: string;
  duration_ms: number;
  start_ms: number;
  points_title: number;
  points_artist: number;
  bonus?: boolean; // ×2 points (title + artist) for this song
  // Editor-only grouping metadata (ignored by the game): which imported playlist
  // a track came from, so the editor can show a compact "playlist — N songs" card.
  source_playlist?: string | null;
  source_playlist_url?: string | null;
}

// Response of GET /api/spotify/playlist.
export interface PlaylistImportResult {
  name: string;
  external_url: string | null;
  track_count: number;
  tracks: Omit<BlindtestTrackDraft, "start_ms" | "points_title" | "points_artist">[];
}

export interface BlindtestTrackNow {
  uri: string;
  start_ms: number;
  title: string;
  artist: string;
  cover_url: string;
}

export interface BlindtestReveal {
  title: string;
  artist: string;
  cover_url: string;
  deltas: Record<string, number>;
}

export interface BlindtestState {
  mode: GameMode;
  state: GameStateName;
  index: number;
  total: number;
  audio: "start" | "resume" | "pause" | null;
  audioSeq: number;   // bumped by the server on every audio transition; drives the host audio effect
  track: BlindtestTrackNow | null;
  reveal: BlindtestReveal | null;
  scoreboard: ScoreboardRow[];
  gameEnd: { podium: PodiumEntry[] } | null;
  partial: { titleBy: string | null; artistBy: string | null };
  // Pause-aware, clock-skew-safe timing (see backend _timing_block).
  segStartedAt: number; // epoch ms (server clock) the current play segment started (incl. countdown)
  endsAt: number;       // epoch ms auto-pause; 0 = no cap / paused
  maxPlayMs: number;    // 0 = no cap
  playedMs: number;     // snippet time consumed in earlier (paused) segments
  playing: boolean;     // whether the snippet clock is currently running
  clockOffset: number;  // server_now - Date.now() at last timing message; add to Date.now() to estimate server time
  bonus: boolean;       // current song is a ×2 bonus
}

export const EMPTY_BLINDTEST: BlindtestState = {
  mode: "buzzer",
  state: "LOBBY",
  index: -1,
  total: 0,
  audio: null,
  audioSeq: 0,
  track: null,
  reveal: null,
  scoreboard: [],
  gameEnd: null,
  partial: { titleBy: null, artistBy: null },
  segStartedAt: 0,
  endsAt: 0,
  maxPlayMs: 0,
  playedMs: 0,
  playing: false,
  clockOffset: 0,
  bonus: false,
};

export interface PlayerInfo {
  id: string;
  pseudo: string;
  score: number;
  connected: boolean;
  rank: number;
}

export interface BuzzEntry {
  player_id: string;
  pseudo: string;
  order: number;
  delta_ms: number;
}

export interface RoundState {
  state: GameStateName;
  question_text: string | null;
  points: number;
  bonus?: boolean; // ×2 round
  image?: string | null; // optional prompt image URL (/media/...)
  revealed: boolean;
  floor_player_id: string | null;
  round_index: number; // -1 = not started / lobby
  round_total: number;
  answer: string | null;
  buzz_open_at?: number; // server ms the buzzer unlocks (after the reading window)
  clockOffset?: number; // server_now - Date.now(), estimated when round_state arrived
}

export interface BuzzState {
  state: GameStateName;
  floor_player_id: string | null;
  queue: BuzzEntry[];
}

export interface RevealInfo {
  answer: string | null;
  correct_player_id: string | null;
  deltas: Record<string, number>;
}

export interface Me {
  id?: string;
  role: "host" | "player" | "tv";
  reconnect_token?: string;
}

export interface GameSnapshot {
  code: string | null;
  you: Me;
  round: RoundState;
  players: PlayerInfo[];
  buzz: BuzzState;
  reveal: RevealInfo | null;
  qcm: QcmState;
  blindtest: BlindtestState;
  connected: boolean;
  error: { code: string; message: string } | null;
}

export const EMPTY_ROUND: RoundState = {
  state: "LOBBY",
  question_text: null,
  points: 1,
  revealed: false,
  floor_player_id: null,
  round_index: -1,
  round_total: 0,
  answer: null,
};
