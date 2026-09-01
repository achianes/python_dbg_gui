import { create } from "zustand";
import { ws } from "../ws/client";
import { Cmd, Evt, type Message } from "../ws/protocol";
import { useStore } from "./store";
import { useDebug } from "./debug";

/** Snapshot the script in the active editor tab (so the AI debugs the real file). */
function activeEditor(): { path: string; content: string } | undefined {
  const st = useStore.getState();
  const f = st.open.find((o) => o.path === st.active);
  if (!f || !f.content.trim()) return undefined;
  return { path: f.path, content: f.content };
}

/** Collect the most recent run's failures + tail of stderr, fed back to the AI. */
function lastRunError(): string | undefined {
  const d = useDebug.getState();
  const parts: string[] = [];
  for (const [idx, b] of Object.entries(d.nlt.blocks ?? {})) {
    if (b.ok === false) {
      const fails = (b.failures ?? []).join("; ") || b.error || "failed";
      parts.push(`block #${idx}: ${fails}`);
    }
  }
  const errLines = d.console
    .filter((l) => l.stream === "err")
    .slice(-12)
    .map((l) => l.text.trimEnd())
    .filter(Boolean);
  if (errLines.length) parts.push("console:\n" + errLines.join("\n"));
  const out = parts.join("\n").trim();
  return out || undefined;
}

export interface Attachment { path: string; kind: string; name: string; }
export interface ChatMsg { role: "user" | "assistant"; text: string; nlt?: string; }

interface ChatState {
  messages: ChatMsg[];
  busy: boolean;
  attachments: Attachment[];
  webOn: boolean;
  toggleWeb: () => void;
  addAttachment: (a: Attachment) => void;
  removeAttachment: (path: string) => void;
  send: (text: string) => void;
  reset: () => void;
  stop: () => void;
  saveChat: () => Promise<string>;
  ingest: (m: Message) => void;
}

export const useChat = create<ChatState>((set, get) => ({
  messages: [],
  busy: false,
  attachments: [],
  webOn: false,

  toggleWeb: () => set((s) => ({ webOn: !s.webOn })),

  addAttachment: (a) =>
    set((s) => ({ attachments: [...s.attachments, a] })),
  removeAttachment: (path) =>
    set((s) => ({ attachments: s.attachments.filter((x) => x.path !== path) })),

  send: (text) => {
    const atts = get().attachments;
    set((s) => ({
      messages: [...s.messages, { role: "user", text }],
      attachments: [],
      busy: true,
    }));
    ws.send(Cmd.CHAT_SEND, {
      text,
      attachments: atts,
      editor: activeEditor(),
      runError: lastRunError(),
      web: get().webOn,
    });
  },

  reset: () => {
    ws.send(Cmd.CHAT_RESET, {});
    set({ messages: [], attachments: [] });
  },

  stop: () => {
    ws.send(Cmd.CHAT_STOP, {});
    set({ busy: false });
  },

  // Export the conversation as a Markdown file in the project root.
  saveChat: async () => {
    const msgs = get().messages;
    const md = msgs
      .map((m) => {
        const who = m.role === "user" ? "## 🧑 You" : "## 🤖 AI";
        const body = m.nlt ? `${m.text}\n\n\`\`\`nlt\n${m.nlt}\n\`\`\`` : m.text;
        return `${who}\n\n${body}`;
      })
      .join("\n\n---\n\n");
    const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
    const path = `chat_${stamp}.md`;
    await import("../api").then(({ api }) => api.write(path, md + "\n"));
    return path;
  },

  ingest: (m) => {
    if (m.type === Evt.CHAT_START) {
      set({ busy: true });
    } else if (m.type === Evt.CHAT_DONE) {
      const p = m.payload as { reply?: string; nlt?: string; stopped?: boolean };
      set((s) => ({
        busy: false,
        // A stopped turn is dropped silently — the user already sees it ended.
        messages: p.stopped
          ? s.messages
          : [...s.messages, { role: "assistant", text: p.reply ?? "", nlt: p.nlt || undefined }],
      }));
    } else if (m.type === Evt.CHAT_ERROR) {
      const p = m.payload as { error?: string };
      set((s) => ({
        busy: false,
        messages: [...s.messages, { role: "assistant", text: "⚠ " + (p.error ?? "error") }],
      }));
    }
  },
}));
