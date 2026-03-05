"""
GNOSIS Oracle — Production Server
FastAPI + WebSocket + GNOSIS agent
Render.com deployment with /data persistent disk
"""
import sys, types
# Python 3.13+ removed imghdr
if "imghdr" not in sys.modules:
    _m = types.ModuleType("imghdr"); _m.what = lambda *a, **kw: None
    sys.modules["imghdr"] = _m

import asyncio
import json
import os
import threading
import time
import traceback
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from queue import Queue, Empty

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

sys.path.append(os.path.abspath('.'))

from src.config import ensure_data_dirs, get_config
ensure_data_dirs()
config = get_config()

# ── Install Playwright browser at runtime if missing ──────────────
def _ensure_playwright_browser():
    import subprocess, shutil
    pw_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH",
              os.path.join(os.path.dirname(__file__), ".playwright"))
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = pw_path
    os.makedirs(pw_path, exist_ok=True)

    # Check if chromium executable already exists
    for root, dirs, files in os.walk(pw_path):
        for f in files:
            if "chrome" in f.lower() and os.access(os.path.join(root, f), os.X_OK):
                print(f"[PW] Chromium found: {os.path.join(root, f)}")
                return  # Already installed

    print("[PW] Chromium not found — installing now...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=False, timeout=300,
            env={**os.environ, "PLAYWRIGHT_BROWSERS_PATH": pw_path}
        )
        subprocess.run(
            [sys.executable, "-m", "playwright", "install-deps", "chromium"],
            capture_output=False, timeout=120,
            env={**os.environ, "PLAYWRIGHT_BROWSERS_PATH": pw_path}
        )
        print("[PW] Chromium installed.")
    except Exception as e:
        print(f"[PW] Install warning: {e}")

_ensure_playwright_browser()

# ── Shared state ──────────────────────────────────────────────────
log_buffer: Queue = Queue()
connected_ws: set = set()

stats = {
    "rounds": 0, "actions": 0, "errors": 0, "decisions": 0,
    "status": "STARTING", "phase": "INIT", "last_action": "",
    "started_at": datetime.now().isoformat(),
}

# ── Log emitter ───────────────────────────────────────────────────
def emit(log_type: str, message: str, section: str = None):
    entry = {
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": log_type,
        "message": str(message),
        "section": section or log_type.upper(),
    }
    log_buffer.put(entry)
    try:
        log_path = config.get("log_path", "/data/logs/gnosis.log")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass

# ── HTTP Routes ───────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(broadcaster())
    asyncio.create_task(stats_broadcaster())
    t = threading.Thread(target=run_agent, daemon=True)
    t.start()
    yield

app = FastAPI(title="GNOSIS Oracle", lifespan=lifespan)

# Serve imgs/ as /imgs/
_imgs_dir = Path(__file__).parent / "imgs"
if _imgs_dir.exists():
    app.mount("/imgs", StaticFiles(directory=str(_imgs_dir)), name="imgs")

@app.get("/")
async def serve_terminal():
    html_path = Path(__file__).parent / "terminal.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>GNOSIS — terminal.html missing</h1>", status_code=500)

@app.get("/health")
async def health():
    return {"status": "ok", "agent": stats["status"], "phase": stats["phase"]}

@app.get("/api/stats")
async def api_stats():
    return JSONResponse(stats)

@app.get("/api/logs")
async def api_logs(n: int = 100):
    log_path = config.get("log_path", "/data/logs/gnosis.log")
    if not os.path.exists(log_path):
        return JSONResponse([])
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        parsed = []
        for line in lines[-n:]:
            try:
                parsed.append(json.loads(line.strip()))
            except Exception:
                parsed.append({"ts": "", "type": "info", "message": line.strip(), "section": "LOG"})
        return JSONResponse(parsed)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/dialog")
async def api_dialog(n: int = 20):
    dialog_path = config.get("dialog_path", "/data/dialog/dialog.jsonl")
    if not os.path.exists(dialog_path):
        return JSONResponse([])
    try:
        with open(dialog_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        parsed = []
        for line in lines[-n:]:
            try:
                parsed.append(json.loads(line.strip()))
            except Exception:
                pass
        return JSONResponse(parsed)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/memory")
async def api_memory():
    memory_path = config.get("memory_path", "/data/memory/memory.json")
    if not os.path.exists(memory_path):
        return JSONResponse([])
    try:
        with open(memory_path, "r", encoding="utf-8") as f:
            return JSONResponse(json.load(f))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# ── WebSocket ─────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global connected_ws
    await websocket.accept()
    connected_ws.add(websocket)
    try:
        await websocket.send_text(json.dumps({
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": "system", "message": "GNOSIS oracle terminal connected.", "section": "SYSTEM",
        }))
        await websocket.send_text(json.dumps({
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": "stats", "message": json.dumps(stats), "section": "STATS",
        }))
        while True:
            await asyncio.sleep(25)
            await websocket.send_text(json.dumps({
                "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "type": "heartbeat", "message": "♦", "section": "HB",
            }))
    except (WebSocketDisconnect, Exception):
        connected_ws.discard(websocket)

# ── Broadcasters ──────────────────────────────────────────────────
async def broadcaster():
    global connected_ws
    while True:
        messages = []
        try:
            while True:
                messages.append(log_buffer.get_nowait())
        except Empty:
            pass
        if messages:
            dead = set()
            for msg in messages:
                payload = json.dumps(msg)
                for ws in list(connected_ws):
                    try:
                        await ws.send_text(payload)
                    except Exception:
                        dead.add(ws)
            connected_ws -= dead
        await asyncio.sleep(0.05)

async def stats_broadcaster():
    global connected_ws
    while True:
        await asyncio.sleep(5)
        if connected_ws:
            payload = json.dumps({
                "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "type": "stats", "message": json.dumps(stats), "section": "STATS",
            })
            dead = set()
            for ws in list(connected_ws):
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead.add(ws)
            connected_ws -= dead

# ── Agent Thread ──────────────────────────────────────────────────
def run_agent():
    time.sleep(3)
    try:
        _run_gnosis()
    except Exception as e:
        emit("error", f"Agent fatal error: {e}\n{traceback.format_exc()[:500]}", "ERROR")
        stats["status"] = "CRASHED"

def _run_gnosis():
    from dotenv import load_dotenv
    load_dotenv()

    from src.actionX import actionX
    from src.decision import decision
    from src.dialogManager import dialogManager
    from src.memory import memory
    from src.observationX import observationX
    from src.logs import logs as LogClass
    from src.claude_ai import claude_ai

    class AgentLogs(LogClass):
        def log_error(self, s):
            super().log_error(s)
            emit("error", s, "ERROR")
            stats["errors"] += 1

        def log_info(self, s, border_style=None, title=None, subtitle=None):
            super().log_info(s, border_style, title, subtitle)
            section = title if title else "INFO"
            emit(section.lower().replace(" ", "_"), s, section)

    emit("system", "GNOSIS awakens. Initializing subsystems...", "SYSTEM")
    stats["status"] = "INITIALIZING"

    ai       = claude_ai()
    action   = actionX()
    dec      = decision(ai)
    dm       = dialogManager()
    mem      = memory()
    obs      = observationX()
    log_inst = AgentLogs()

    emit("system", f"All systems online. Model: {config['llm_settings']['claude']['model']}", "SYSTEM")
    stats["status"] = "ACTIVE"

    import pandas as _pd

    def _do_action(result, label=""):
        """Execute one decision and emit to frontend."""
        action.excute(result)
        action_type    = result.get('action','post')
        action_content = str(result.get('content',''))
        action_summary = f"{action_type} — {action_content[:120]}"
        emit("transmit", action_summary, "TRANSMIT")
        stats["actions"] += 1
        stats["last_action"] = action_summary
        dm.write_dialog(result)
        if label:
            emit("system", label, "SYSTEM")

    while True:
        try:
            memory_ctx = mem.quer_memory()
            dialog_ctx = dm.read_dialog()

            # ── PHASE 1: CHECK MENTIONS ──────────────────────────
            # Check if anyone has spoken to GNOSIS and reply to each
            stats["phase"] = "MENTIONS"
            emit("system", "Checking mentions...", "SYSTEM")
            try:
                mentions_df = obs.xBridge_instance._get_mentions(count=5)
                if mentions_df is not None and not mentions_df.empty:
                    log_inst.log_info(f"{len(mentions_df)} mention(s) found", "bold green", "Mentions")
                    for _, mention_row in mentions_df.iterrows():
                        try:
                            # Build a single-row df for this mention
                            single = _pd.DataFrame([mention_row])
                            stats["phase"] = "DECIDING"
                            result = dec.make_decision(single, memory_ctx, dialog_ctx)
                            log_inst.log_info(str(result), "dim magenta", "Decision")
                            stats["decisions"] += 1
                            stats["phase"] = "ACTING"
                            _do_action(result, f"Replied to mention from @{mention_row.get('Handle','?')}")
                        except Exception as me:
                            emit("error", f"Mention reply error: {me}", "ERROR")
                else:
                    emit("system", "No new mentions", "SYSTEM")
            except Exception as me:
                emit("error", f"Mentions check error: {me}", "ERROR")

            # ── PHASE 2: OBSERVE TIMELINE + POST ────────────────
            stats["phase"] = "OBSERVING"
            emit("system", "Observing the stream...", "SYSTEM")
            observation = obs.get()
            log_inst.log_info(str(observation), "bold green", "Observation")

            log_inst.log_info(str(memory_ctx) or "[empty]", "dim cyan", "Memory")
            log_inst.log_info(str(dialog_ctx), "dim cyan", "Dialog")

            stats["phase"] = "DECIDING"
            emit("system", "Oracle deciding...", "SYSTEM")
            result = dec.make_decision(observation, memory_ctx, dialog_ctx)
            log_inst.log_info(str(result), "dim magenta", "Decision")
            stats["decisions"] += 1

            stats["phase"] = "ACTING"
            _do_action(result)

            stats["rounds"] += 1
            stats["phase"] = "DORMANT"
            interval = config.get('interval_time', 300)
            emit("system", f"Round {stats['rounds']} complete. Next in {interval}s.", "SYSTEM")

        except Exception as e:
            emit("error", f"Oracle disruption: {e}", "ERROR")
            emit("error", traceback.format_exc()[:400], "TRACE")
            stats["errors"] += 1
            stats["phase"] = "ERROR_RECOVERY"

        time.sleep(config.get('interval_time', 300))

# ── Entry point ───────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
