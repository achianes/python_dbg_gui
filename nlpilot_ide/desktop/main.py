"""Desktop shell: start the backend in a thread, open a pywebview window on it.

`nlpilot-ide` (console entry point) → native window loading the local server.
Falls back to a clear message if the frontend isn't built yet.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from urllib.request import urlopen

import uvicorn
import webview

from ..server.run import HOST, PORT

_URL = f"http://{HOST}:{PORT}"

# Persisted window geometry (size + position + maximized), so the desktop window
# reopens where the user left it.
_WIN_FILE = Path.home() / ".nlpilot_ide" / "window.json"


def _load_geometry() -> dict:
    try:
        g = json.loads(_WIN_FILE.read_text(encoding="utf-8"))
        return g if isinstance(g, dict) else {}
    except Exception:  # noqa: BLE001 — first run / no file
        return {}


def _save_geometry(g: dict) -> None:
    try:
        _WIN_FILE.parent.mkdir(parents=True, exist_ok=True)
        _WIN_FILE.write_text(json.dumps(g), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def _serve() -> None:
    uvicorn.run("nlpilot_ide.server.app:app", host=HOST, port=PORT, log_level="warning")


def _wait_for_server(timeout: float = 10.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urlopen(f"{_URL}/api/health", timeout=0.5)
            return True
        except Exception:  # noqa: BLE001
            time.sleep(0.1)
    return False


class _Api:
    """Exposed to the web app as window.pywebview.api — native dialogs, etc.

    NOTE: the window reference is a PRIVATE (underscore) attribute on purpose.
    pywebview enumerates public attributes of this object to expose them to JS and
    recurses into non-callable ones; a public `window` would make it descend into
    the pywebview Window (a .NET object under the EdgeChromium backend) and crash
    with "'_Api' value cannot be converted to System.Drawing.Rectangle". The
    leading underscore makes pywebview skip it.
    """

    def __init__(self) -> None:
        self._window = None

    def pick_folder(self):
        """Open the OS folder picker; return the chosen absolute path or None."""
        if not self._window:
            return None
        result = self._window.create_file_dialog(webview.FOLDER_DIALOG)
        if result:
            return result[0]
        return None


def main() -> None:
    # Spawn debug subprocesses with pythonw on Windows so no console window flashes.
    import sys
    if sys.platform == "win32":
        import multiprocessing
        import os

        pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if os.path.exists(pyw):
            multiprocessing.set_executable(pyw)

    t = threading.Thread(target=_serve, daemon=True)
    t.start()
    if not _wait_for_server():
        raise RuntimeError("backend did not start in time")
    api = _Api()
    geo = _load_geometry()
    kwargs = dict(width=int(geo.get("width", 1400)), height=int(geo.get("height", 900)))
    if geo.get("x") is not None and geo.get("y") is not None:
        kwargs["x"], kwargs["y"] = int(geo["x"]), int(geo["y"])
    if geo.get("maximized"):
        kwargs["maximized"] = True
    window = webview.create_window(
        "nlpilot-ide", _URL, js_api=api,
        text_select=True,  # allow selecting/copying console output etc.
        **kwargs,
    )
    api._window = window

    # Track live geometry via events and persist it when the window closes.
    state = {
        "width": kwargs["width"], "height": kwargs["height"],
        "x": geo.get("x"), "y": geo.get("y"), "maximized": bool(geo.get("maximized")),
    }

    def _on_resized(*a):
        if len(a) >= 2:
            try:
                state["width"], state["height"] = int(a[0]), int(a[1])
            except Exception:  # noqa: BLE001
                pass

    def _on_moved(*a):
        if len(a) >= 2:
            try:
                state["x"], state["y"] = int(a[0]), int(a[1])
            except Exception:  # noqa: BLE001
                pass

    def _on_maximized(*a):
        state["maximized"] = True

    def _on_restored(*a):
        state["maximized"] = False

    def _on_closing(*a):
        _save_geometry(state)

    # Event names vary across pywebview versions/backends — bind defensively.
    # pywebview Event objects append handlers via `+= handler`.
    for ev, cb in (
        ("resized", _on_resized), ("moved", _on_moved),
        ("maximized", _on_maximized), ("restored", _on_restored),
        ("closing", _on_closing), ("closed", _on_closing),
    ):
        try:
            evt = getattr(window.events, ev)
            evt += cb
        except Exception:  # noqa: BLE001 — this pywebview build lacks the event
            pass

    webview.start()
    # Belt-and-suspenders: also save after the event loop returns.
    _save_geometry(state)


if __name__ == "__main__":
    main()
