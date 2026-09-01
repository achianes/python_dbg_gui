// Server-side persistence of the UI layout (panel visibility + split sizes).
// localStorage is the live source the components read; we hydrate it from the
// server before first render, and mirror any change back to the server (debounced)
// so the layout survives even when the desktop webview does not keep localStorage.
import { api } from "./api";

const KEY_RE = /^(ide:|split:)/;

/** Snapshot every layout-related localStorage entry. */
function snapshot(): Record<string, string> {
  const out: Record<string, string> = {};
  for (let i = 0; i < localStorage.length; i++) {
    const k = localStorage.key(i);
    if (k && KEY_RE.test(k)) out[k] = localStorage.getItem(k) ?? "";
  }
  return out;
}

/** Load the saved layout from the server and write it into localStorage BEFORE the
 *  React tree mounts, so useState/useSplitSize initializers pick it up. */
export async function loadLayout(): Promise<void> {
  try {
    const saved = await api.getLayout();
    for (const [k, v] of Object.entries(saved || {})) {
      if (KEY_RE.test(k)) localStorage.setItem(k, v);
    }
  } catch {
    /* offline / first run — keep whatever localStorage already has */
  }
}

let timer: ReturnType<typeof setTimeout> | null = null;

/** Debounced push of the current layout to the server. */
export function saveLayout(): void {
  if (timer) clearTimeout(timer);
  timer = setTimeout(() => {
    api.saveLayout(snapshot()).catch(() => {});
  }, 400);
}
