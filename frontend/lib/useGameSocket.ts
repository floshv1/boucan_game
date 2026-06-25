"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { EMPTY_BLINDTEST, EMPTY_QCM, EMPTY_ROUND, GameSnapshot, Me } from "./types";

interface Params {
  code: string;
  role: "host" | "player" | "tv";
  pseudo?: string;
  hostSecret?: string;
  enabled?: boolean;
}

// The WebSocket goes straight to the backend port, derived from the hostname the
// page was loaded with. A phone that opened http://192.168.x.x:3200 will reach
// ws://192.168.x.x:8200/ws — no per-device config (cahier §2 scénario A).
function backendWsUrl(): string {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  const port = process.env.NEXT_PUBLIC_BACKEND_PORT ?? "8200";
  return `${proto}://${window.location.hostname}:${port}/ws`;
}

const rtKey = (code: string) => `quiz:rt:${code}`;

// Extract the pause-aware timing block (see backend _timing_block) from a payload,
// falling back to the previous values when a field is absent. ``clockOffset`` is
// recomputed whenever the server sends ``server_now`` so countdown/progress stay
// correct even when the host clock differs from the backend.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function btTiming(p: any, prev: GameSnapshot["blindtest"]) {
  return {
    segStartedAt: p.seg_started_at ?? p.starts_at ?? prev.segStartedAt,
    endsAt: p.ends_at ?? prev.endsAt,
    maxPlayMs: p.max_play_ms ?? prev.maxPlayMs,
    playedMs: p.played_ms ?? prev.playedMs,
    playing: p.playing ?? prev.playing,
    audioSeq: p.audio_seq ?? prev.audioSeq,
    bonus: p.bonus ?? prev.bonus,
    clockOffset:
      p.server_now !== undefined ? p.server_now - Date.now() : prev.clockOffset,
  };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function reduce(s: GameSnapshot, msg: any, code: string): GameSnapshot {
  const p = msg.payload ?? {};
  switch (msg.type) {
    case "state_sync": {
      const you: Me = p.you ?? { role: s.you.role };
      if (you.reconnect_token) localStorage.setItem(rtKey(code), you.reconnect_token);
      return {
        ...s,
        code: p.code ?? code,
        you: { ...s.you, ...you },
        round: p.round
          ? {
              ...p.round,
              clockOffset:
                p.round.server_now !== undefined ? p.round.server_now - Date.now() : s.round.clockOffset ?? 0,
            }
          : s.round,
        players: p.player_list?.players ?? s.players,
        buzz: p.buzz ?? s.buzz,
        reveal: p.round?.revealed ? s.reveal : null,
        qcm: p.qcm
          ? {
              ...s.qcm,
              mode: p.qcm.mode,
              state: p.qcm.state,
              index: p.qcm.index,
              total: p.qcm.total,
              question: p.qcm.question ?? null,
              progress: p.qcm.progress ?? s.qcm.progress,
              gameEnd: p.qcm.game_end ?? null,
              myChoice: p.qcm.my_choice ?? null,
              clockOffset:
                p.qcm.question?.server_now !== undefined
                  ? p.qcm.question.server_now - Date.now()
                  : s.qcm.clockOffset,
            }
          : s.qcm,
        blindtest: p.blindtest
          ? {
              ...s.blindtest,
              mode: p.blindtest.mode,
              state: p.blindtest.state,
              index: p.blindtest.index,
              total: p.blindtest.total,
              audio: p.blindtest.audio ?? s.blindtest.audio,
              track: p.blindtest.uri
                ? {
                    uri: p.blindtest.uri,
                    start_ms: p.blindtest.start_ms,
                    title: p.blindtest.title,
                    artist: p.blindtest.artist,
                    cover_url: p.blindtest.cover_url,
                  }
                : null,
              reveal: p.blindtest.reveal ?? null,
              gameEnd: p.blindtest.game_end ?? s.blindtest.gameEnd,
              ...btTiming(p.blindtest, s.blindtest),
            }
          : s.blindtest,
      };
    }
    case "player_list":
      return { ...s, players: p.players ?? s.players };
    case "round_state":
      return {
        ...s,
        round: {
          ...p,
          clockOffset: p.server_now !== undefined ? p.server_now - Date.now() : s.round.clockOffset ?? 0,
        },
        reveal: p.revealed ? s.reveal : null,
      };
    case "buzz_locked":
      return { ...s, buzz: p };
    case "bt_track": {
      const hasTrackFields =
        p.title !== undefined && p.artist !== undefined;
      return {
        ...s,
        blindtest: {
          ...s.blindtest,
          mode: "blindtest",
          state: "BUZZER_OPEN",
          index: p.index,
          total: p.total,
          reveal: null,
          partial: { titleBy: null, artistBy: null },
          track: hasTrackFields
            ? {
                uri: p.uri,
                start_ms: p.start_ms,
                title: p.title,
                artist: p.artist,
                cover_url: p.cover_url ?? "",
              }
            : null,
          audio: p.audio ?? s.blindtest.audio,
          ...btTiming(p, s.blindtest),
        },
      };
    }
    case "bt_audio":
      return {
        ...s,
        blindtest: { ...s.blindtest, audio: p.audio, ...btTiming(p, s.blindtest) },
      };
    case "bt_partial":
      return {
        ...s,
        blindtest: {
          ...s.blindtest,
          partial: { titleBy: p.title_by ?? null, artistBy: p.artist_by ?? null },
        },
      };
    case "question_start":
      return {
        ...s,
        qcm: {
          ...s.qcm,
          mode: "qcm",
          state: "QUESTION_ACTIVE",
          index: p.index,
          total: p.total,
          question: p,
          reveal: null,
          progress: { answered: 0, total: s.qcm.progress.total },
          myChoice: null,
          // Clock skew: the server stamps server_now on the question; comparing it
          // to our receipt time gives the offset used by the reading + answer timers.
          clockOffset:
            p.server_now !== undefined ? p.server_now - Date.now() : s.qcm.clockOffset,
        },
      };
    case "qcm_progress":
      return { ...s, qcm: { ...s.qcm, progress: p } };
    case "answer_ack":
      return { ...s, qcm: { ...s.qcm, myChoice: p.choice } };
    case "reveal":
      // Blindtest reveal carries title/artist; QCM reveal carries distribution; buzzer reveal does not.
      if (p.title !== undefined && p.artist !== undefined) {
        return {
          ...s,
          blindtest: {
            ...s.blindtest,
            state: "REVEAL",
            reveal: {
              title: p.title,
              artist: p.artist,
              cover_url: p.cover_url ?? "",
              deltas: p.deltas ?? {},
            },
          },
        };
      }
      if (p.distribution !== undefined) {
        return { ...s, qcm: { ...s.qcm, state: "REVEAL", reveal: p } };
      }
      return { ...s, reveal: p };
    case "scoreboard":
      return {
        ...s,
        qcm: { ...s.qcm, state: "SCOREBOARD", scoreboard: p.players ?? [] },
        blindtest: { ...s.blindtest, state: "SCOREBOARD", scoreboard: p.players ?? [] },
      };
    case "game_end":
      return {
        ...s,
        qcm: { ...s.qcm, state: "GAME_END", gameEnd: p },
        blindtest: { ...s.blindtest, state: "GAME_END", gameEnd: { podium: p.podium ?? [] } },
      };
    case "error":
      return { ...s, error: p };
    default:
      return s;
  }
}

export function useGameSocket({ code, role, pseudo, hostSecret, enabled = true }: Params) {
  const [snapshot, setSnapshot] = useState<GameSnapshot>(() => ({
    code,
    you: { role },
    round: EMPTY_ROUND,
    players: [],
    buzz: { state: "LOBBY", floor_player_id: null, queue: [] },
    reveal: null,
    qcm: EMPTY_QCM,
    blindtest: EMPTY_BLINDTEST,
    connected: false,
    error: null,
  }));

  const wsRef = useRef<WebSocket | null>(null);
  const pingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const stopRef = useRef(false);

  const send = useCallback((type: string, payload: Record<string, unknown> = {}) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type, payload, ts: Date.now() }));
    }
  }, []);

  useEffect(() => {
    if (!enabled || !code) return;
    stopRef.current = false;

    const connect = () => {
      const ws = new WebSocket(backendWsUrl());
      wsRef.current = ws;

      ws.onopen = () => {
        const joinPayload: Record<string, unknown> = { code, role };
        if (role === "host") {
          joinPayload.host_secret = hostSecret;
        } else if (role === "player") {
          joinPayload.pseudo = pseudo;
          const stored = localStorage.getItem(rtKey(code));
          if (stored) joinPayload.reconnect_token = stored;
        }
        // role "tv": a bare spectator join, no pseudo/secret/token
        ws.send(JSON.stringify({ type: "join", payload: joinPayload, ts: Date.now() }));
        setSnapshot((s) => ({ ...s, connected: true, error: null }));

        if (pingRef.current) clearInterval(pingRef.current);
        pingRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "ping", payload: {}, ts: Date.now() }));
          }
        }, 15000);
      };

      ws.onmessage = (ev) => {
        let msg: unknown;
        try {
          msg = JSON.parse(ev.data);
        } catch {
          return;
        }
        setSnapshot((s) => reduce(s, msg, code));
      };

      ws.onclose = (ev) => {
        if (pingRef.current) clearInterval(pingRef.current);
        setSnapshot((s) => ({ ...s, connected: false }));
        // 4000 = kicked by host → stay out
        if (!stopRef.current && ev.code !== 4000) {
          reconnectRef.current = setTimeout(connect, 1500);
        }
      };
    };

    connect();

    return () => {
      stopRef.current = true;
      if (pingRef.current) clearInterval(pingRef.current);
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      wsRef.current?.close();
    };
  }, [code, role, pseudo, hostSecret, enabled]);

  return { snapshot, send };
}
