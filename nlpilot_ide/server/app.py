"""FastAPI app: WebSocket hub + static frontend serving.

Phase 0: a single WS endpoint that says hello on connect and answers ping with
pong. Static files are the built Vite bundle in web/dist (served when present),
so the same server backs both `nlpilot-ide` desktop and browser modes.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from fastapi import (
    Body, FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect,
)
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from .controller import DebugController
from .engines.chat_engine import ChatEngine
from .project import Project, ProjectError
from .ws_protocol import Cmd, Evt, Message

logger = logging.getLogger("nlpilot_ide")

# web/dist relative to repo root (this file: nlpilot_ide/server/app.py)
_WEB_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"


def create_app(root: str | Path | None = None) -> FastAPI:
    app = FastAPI(title="nlpilot-ide", version="0.1.0")
    root = root or os.environ.get("NLPILOT_IDE_ROOT") or Path.cwd()
    project = Project(root)
    # One chat engine for the whole app (not per WebSocket) so the conversation
    # SURVIVES a page reload or a dropped/reconnected socket — the history lives here.
    chat = ChatEngine(project)

    @app.get("/api/health")
    async def health() -> JSONResponse:
        return JSONResponse({"ok": True, "web_dist": _WEB_DIST.exists()})

    # ---- UI layout persistence (panel visibility + split sizes) ----
    # Stored server-side so it survives even when the desktop webview does not keep
    # localStorage across sessions. One global file per user.
    _layout_file = Path.home() / ".nlpilot_ide" / "layout.json"

    @app.get("/api/layout")
    async def get_layout() -> JSONResponse:
        try:
            import json as _json
            return JSONResponse(_json.loads(_layout_file.read_text(encoding="utf-8")))
        except Exception:  # noqa: BLE001 — no saved layout yet
            return JSONResponse({})

    @app.put("/api/layout")
    async def put_layout(layout: dict = Body(...)) -> JSONResponse:
        try:
            import json as _json
            _layout_file.parent.mkdir(parents=True, exist_ok=True)
            _layout_file.write_text(_json.dumps(layout), encoding="utf-8")
            return JSONResponse({"ok": True})
        except Exception as e:  # noqa: BLE001
            return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

    # ---- project / file API ----
    @app.get("/api/root")
    async def get_root() -> JSONResponse:
        return JSONResponse({"root": str(project.root)})

    @app.post("/api/root")
    async def set_root(path: str = Body(..., embed=True)) -> JSONResponse:
        try:
            project.set_root(path)
        except ProjectError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return JSONResponse({"root": str(project.root)})

    @app.get("/api/tree")
    async def get_tree() -> JSONResponse:
        return JSONResponse(project.tree().to_dict())

    @app.post("/api/pick-folder")
    async def pick_folder() -> JSONResponse:
        # Native OS folder chooser (tkinter, run in a subprocess so it never
        # touches the server's own event loop / GUI thread). Blocks until the
        # user picks or cancels; returns "" on cancel.
        path = await asyncio.to_thread(_native_pick_folder)
        return JSONResponse({"path": path})

    @app.get("/api/file")
    async def get_file(path: str) -> JSONResponse:
        try:
            return JSONResponse({"path": path, "content": project.read(path)})
        except ProjectError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.put("/api/file")
    async def put_file(
        path: str = Body(...), content: str = Body(...)
    ) -> JSONResponse:
        try:
            project.write(path, content)
        except ProjectError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return JSONResponse({"ok": True, "path": path})

    @app.post("/api/upload")
    async def upload(file: UploadFile = File(...)) -> JSONResponse:
        # Save a chat attachment (requirement doc or UI screenshot) under the project's
        # hidden scratch dir; the returned path is passed back in a chat.send payload.
        data = await file.read()
        if len(data) > 20_000_000:
            raise HTTPException(status_code=400, detail="file too large (>20MB)")
        try:
            rel = project.save_upload(file.filename or "file", data)
        except ProjectError as e:
            raise HTTPException(status_code=400, detail=str(e))
        ext = (file.filename or "").lower().rsplit(".", 1)[-1]
        kind = "image" if ext in {"png", "jpg", "jpeg", "gif", "webp", "bmp"} else "doc"
        return JSONResponse({"path": rel, "kind": kind, "name": file.filename})

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket) -> None:
        await ws.accept()
        await ws.send_json(Message(Evt.HELLO, {"version": "0.1.0"}).to_dict())
        controller = DebugController(project)

        async def pump() -> None:
            # Drain engine events and forward them to the client.
            while True:
                for m in controller.poll():
                    await ws.send_json(m)
                await asyncio.sleep(0.03)

        pump_task = asyncio.create_task(pump())
        try:
            while True:
                raw = await ws.receive_json()
                msg = Message.from_dict(raw)
                # Generate is slow (LLM) — run off the event loop.
                if msg.type == Cmd.NLT_GENERATE:
                    try:
                        blocks = await asyncio.to_thread(
                            controller.generate_blocks, msg.payload.get("path", "")
                        )
                        await ws.send_json(
                            Message(Evt.NLT_GENERATED, {"blocks": blocks}).to_dict()
                        )
                    except Exception as e:  # noqa: BLE001
                        await ws.send_json(
                            Message(Evt.ERROR, {"reason": f"generate failed: {e}"}).to_dict()
                        )
                    continue
                # AI chat is slow (LLM + optional vision) — run off the event loop.
                if msg.type == Cmd.CHAT_RESET:
                    chat.reset()
                    continue
                if msg.type == Cmd.CHAT_STOP:
                    chat.cancel()  # abort the running generation (streamed)
                    continue
                if msg.type == Cmd.CHAT_SEND:
                    await ws.send_json(Message(Evt.CHAT_START, {}).to_dict())
                    try:
                        result = await asyncio.to_thread(
                            chat.send,
                            msg.payload.get("text", ""),
                            msg.payload.get("attachments", []),
                            msg.payload.get("editor"),
                            msg.payload.get("runError"),
                            bool(msg.payload.get("web")),
                        )
                        await ws.send_json(Message(Evt.CHAT_DONE, result).to_dict())
                    except Exception as e:  # noqa: BLE001
                        await ws.send_json(
                            Message(Evt.CHAT_ERROR, {"error": str(e)}).to_dict()
                        )
                    continue
                reply = controller.handle(msg)
                if reply is not None:
                    await ws.send_json(reply.to_dict())
        except WebSocketDisconnect:
            logger.info("ws client disconnected")
        finally:
            pump_task.cancel()
            controller._stop()

    # Mount the built frontend last so /ws and /api win. Only if built.
    if _WEB_DIST.exists():
        app.mount("/", StaticFiles(directory=str(_WEB_DIST), html=True), name="web")
    else:
        @app.get("/")
        async def _no_build() -> JSONResponse:
            return JSONResponse(
                {"error": "frontend not built", "hint": "cd web && npm install && npm run build"},
                status_code=503,
            )

    return app


def _native_pick_folder() -> str:
    """Show a native 'choose folder' dialog via a short tkinter subprocess and
    return the selected absolute path ('' if cancelled)."""
    import subprocess
    import sys

    code = (
        "import tkinter, tkinter.filedialog as fd;"
        "r=tkinter.Tk(); r.withdraw();"
        "r.attributes('-topmost', True);"
        "p=fd.askdirectory(title='Select project folder');"
        "print(p or '')"
    )
    try:
        out = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=300,
        )
        return out.stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


app = create_app()
