import { useEffect, useRef, useState } from "react";
import { useChat } from "../state/chat";
import { useStore } from "../state/store";
import { api } from "../api";

/** AI chat: describe a task, attach requirement docs / UI screenshots, get a .nlt
 *  script you can drop straight into the editor. */
export function ChatPanel({ width }: { width: number }) {
  const messages = useChat((s) => s.messages);
  const busy = useChat((s) => s.busy);
  const attachments = useChat((s) => s.attachments);
  const send = useChat((s) => s.send);
  const reset = useChat((s) => s.reset);
  const addAttachment = useChat((s) => s.addAttachment);
  const removeAttachment = useChat((s) => s.removeAttachment);
  const webOn = useChat((s) => s.webOn);
  const toggleWeb = useChat((s) => s.toggleWeb);
  const stop = useChat((s) => s.stop);
  const saveChat = useChat((s) => s.saveChat);
  const messagesCount = messages.length;

  const copy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // clipboard API blocked (some webviews) — fall back to a temporary textarea
      const ta = document.createElement("textarea");
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand("copy"); } catch { /* ignore */ }
      ta.remove();
    }
  };

  const [text, setText] = useState("");
  const [uploading, setUploading] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [messages, busy]);

  const submit = () => {
    const t = text.trim();
    if (!t && attachments.length === 0) return;
    send(t || "(vedi allegati)");
    setText("");
  };

  const onFiles = async (files: FileList | null) => {
    if (!files?.length) return;
    setUploading(true);
    try {
      for (const f of Array.from(files)) {
        const r = await api.upload(f);
        addAttachment({ path: r.path, kind: r.kind, name: r.name });
      }
    } catch (e: any) {
      window.alert("Upload failed: " + (e?.message ?? e));
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  };

  const insertScript = async (nlt: string) => {
    const raw = window.prompt("Save the script as (relative to the project root):", "generated.nlt");
    if (!raw) return;
    const rel = raw.trim().replace(/\\/g, "/").replace(/^\/+/, "");
    if (!rel || rel.includes("..")) { window.alert("Invalid file name."); return; }
    try {
      await useStore.getState().newFile(rel, nlt.endsWith("\n") ? nlt : nlt + "\n");
    } catch (e: any) {
      window.alert("Could not create file:\n" + (e?.message ?? e));
    }
  };

  return (
    <aside className="chat-pane" style={{ width, flex: "0 0 auto" }}>
      <div className="chat-head">
        <span>AI CHAT</span>
        <div className="chat-head-btns">
          <button
            className="chat-clear"
            title="Save the conversation as a Markdown file in the project"
            disabled={messagesCount === 0}
            onClick={async () => {
              try {
                const p = await saveChat();
                window.alert("Chat salvata in: " + p);
              } catch (e: any) {
                window.alert("Save failed: " + (e?.message ?? e));
              }
            }}
          >
            💾 Save
          </button>
          <button className="chat-clear" title="Clear conversation" onClick={reset}>Clear</button>
        </div>
      </div>

      <div className="chat-msgs" ref={listRef}>
        {messages.length === 0 && (
          <div className="chat-empty">
            Describe what to automate — e.g. <em>"open WhatsApp on Windows and message
            John"</em>. Attach a requirements doc or a screenshot of the UI, and I'll
            write the <code>.nlt</code> script.
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`chat-msg ${m.role}`}>
            <div className="chat-role">
              <span>{m.role === "user" ? "You" : "AI"}</span>
              <button
                className="chat-copy"
                title="Copy this message"
                onClick={() => copy(m.nlt ? `${m.text}\n\n${m.nlt}` : m.text)}
              >
                ⧉ Copy
              </button>
            </div>
            <div className="chat-text">{m.text}</div>
            {m.nlt && (
              <div className="chat-nlt">
                <pre>{m.nlt}</pre>
                <div className="chat-nlt-btns">
                  <button className="chat-insert" onClick={() => insertScript(m.nlt!)}>
                    ＋ Create .nlt file
                  </button>
                  <button className="chat-insert alt" onClick={() => copy(m.nlt!)}>
                    ⧉ Copy code
                  </button>
                </div>
              </div>
            )}
          </div>
        ))}
        {busy && <div className="chat-msg assistant"><div className="chat-role">AI</div><div className="chat-text chat-typing">thinking…</div></div>}
      </div>

      {attachments.length > 0 && (
        <div className="chat-atts">
          {attachments.map((a) => (
            <span key={a.path} className={`chat-att ${a.kind}`} title={a.path}>
              {a.kind === "image" ? "🖼" : "📄"} {a.name}
              <button onClick={() => removeAttachment(a.path)}>✕</button>
            </span>
          ))}
        </div>
      )}

      <div className="chat-input">
        <textarea
          value={text}
          placeholder="Describe the automation…  (Enter to send, Shift+Enter = newline)"
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); }
          }}
        />
        <div className="chat-actions">
          <input
            ref={fileInput}
            type="file"
            multiple
            style={{ display: "none" }}
            accept=".txt,.md,.pdf,.doc,.docx,.json,.csv,image/*"
            onChange={(e) => onFiles(e.target.files)}
          />
          <button
            className={`chat-attach ${webOn ? "on" : ""}`}
            title={webOn ? "Web search: ON — this message searches the internet" : "Web search: OFF — click to search the internet for this message"}
            onClick={toggleWeb}
          >
            🌐
          </button>
          <button
            className="chat-attach"
            title="Attach a requirements doc or a UI screenshot"
            disabled={uploading}
            onClick={() => fileInput.current?.click()}
          >
            {uploading ? "…" : "📎"}
          </button>
          {busy ? (
            <button className="chat-send stop" onClick={stop} title="Stop the request">
              ⏹ Stop
            </button>
          ) : (
            <button className="chat-send" onClick={submit}>Send</button>
          )}
        </div>
      </div>
    </aside>
  );
}
