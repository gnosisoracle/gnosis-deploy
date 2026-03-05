"""
GNOSIS Oracle — Production Server
FastAPI + WebSocket + GNOSIS agent
Designed for Render.com with /data persistent disk
"""
import types
import asyncio
import json
import os
import sys
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
from queue import Queue, Empty

# ── Python 3.13+ compatibility: imghdr was removed ───────────────
if "imghdr" not in __import__("sys").modules:
    _m = types.ModuleType("imghdr"); _m.what = lambda *a, **kw: None
    __import__("sys").modules["imghdr"] = _m

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse

sys.path.append(os.path.abspath('.'))

# ── Startup Chrome diagnostic ─────────────────────────────────────
import subprocess as _sp
print("[STARTUP] Chrome probe:")
for _c in ["google-chrome-stable","google-chrome","chromium","chromium-browser"]:
    try:
        _r = _sp.run(["which",_c],capture_output=True,text=True)
        if _r.returncode==0: print(f"  which {_c} -> {_r.stdout.strip()}")
    except: pass
try:
    _r = _sp.run(["find","/usr","/opt","-name","google-chrome*","-type","f"],capture_output=True,text=True,timeout=8)
    if _r.stdout.strip(): print(f"  find: {_r.stdout.strip()}")
except: pass

# ── Ensure /data dirs exist before anything else ──────────────────
from src.config import ensure_data_dirs, get_config
ensure_data_dirs()
config = get_config()

app = FastAPI(title="GNOSIS Oracle")

# ── Shared state ──────────────────────────────────────────────────
log_buffer: Queue = Queue()
connected_ws: set = set()

# Stats persisted in memory (reset on restart — hard stats are in /data)
stats = {
    "rounds": 0,
    "actions": 0,
    "errors": 0,
    "decisions": 0,
    "tokens": 0,
    "status": "STARTING",
    "phase": "INIT",
    "last_action": "",
    "started_at": datetime.now().isoformat(),
}

# ── Log emitter ───────────────────────────────────────────────────
def emit(log_type: str, message: str, section: str = None):
    """Thread-safe — called from agent thread"""
    entry = {
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": log_type,
        "message": str(message),
        "section": section or log_type.upper(),
    }
    log_buffer.put(entry)

    # Also append to persistent log file
    try:
        log_path = config.get("log_path", "/data/logs/gnosis.log")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass

# ── HTTP Routes ───────────────────────────────────────────────────
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
    """Return last N log lines from persistent file"""
    log_path = config.get("log_path", "/data/logs/gnosis.log")
    if not os.path.exists(log_path):
        return JSONResponse([])
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        recent = lines[-n:]
        parsed = []
        for line in recent:
            try:
                parsed.append(json.loads(line.strip()))
            except Exception:
                parsed.append({"ts": "", "type": "info", "message": line.strip(), "section": "LOG"})
        return JSONResponse(parsed)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/dialog")
async def api_dialog(n: int = 20):
    """Return last N dialog entries"""
    dialog_path = config.get("dialog_path", "/data/dialog/dialog.jsonl")
    if not os.path.exists(dialog_path):
        return JSONResponse([])
    try:
        with open(dialog_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        recent = lines[-n:]
        parsed = []
        for line in recent:
            try:
                parsed.append(json.loads(line.strip()))
            except Exception:
                pass
        return JSONResponse(parsed)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/memory")
async def api_memory():
    """Return full memory store"""
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
    await websocket.accept()
    connected_ws.add(websocket)

    # Send welcome + current stats
    await websocket.send_text(json.dumps({
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": "system",
        "message": "GNOSIS oracle terminal connected.",
        "section": "SYSTEM",
    }))
    await websocket.send_text(json.dumps({
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": "stats",
        "message": json.dumps(stats),
        "section": "STATS",
    }))

    try:
        while True:
            await asyncio.sleep(25)
            await websocket.send_text(json.dumps({
                "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "type": "heartbeat",
                "message": "♦",
                "section": "HB",
            }))
    except (WebSocketDisconnect, Exception):
        connected_ws.discard(websocket)

# ── Broadcaster ───────────────────────────────────────────────────
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

# ── Stats broadcaster (every 5s) ──────────────────────────────────
async def stats_broadcaster():
    global connected_ws
    while True:
        await asyncio.sleep(5)
        if connected_ws:
            payload = json.dumps({
                "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "type": "stats",
                "message": json.dumps(stats),
                "section": "STATS",
            })
            dead = set()
            for ws in list(connected_ws):
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead.add(ws)
            connected_ws -= dead

@app.on_event("startup")
async def startup():
    asyncio.create_task(broadcaster())
    asyncio.create_task(stats_broadcaster())
    t = threading.Thread(target=run_agent, daemon=True)
    t.start()

# ── GNOSIS Agent Thread ───────────────────────────────────────────
def run_agent():
    time.sleep(3)  # Let server start
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
    from src.logs import logs
    from src.claude_ai import claude_ai

    # Patched logs class that also emits to WS
    class AgentLogs(logs):
        def log_error(self, s):
            super().log_error(s)
            emit("error", s, "ERROR")
            stats["errors"] += 1

        def log_info(self, s, border_style=None, title=None, subtitle=None):
            super().log_info(s, border_style, title, subtitle)
            section = title if title else "INFO"
            t = section.lower().replace(" ", "_")
            emit(t, s, section)

    emit("system", "GNOSIS awakens. Initializing all subsystems...", "SYSTEM")
    stats["status"] = "INITIALIZING"
    stats["phase"] = "BOOT"

    ai       = claude_ai()
    action   = actionX()
    dec      = decision(ai)
    dm       = dialogManager()
    mem      = memory()
    obs      = observationX()
    log_inst = AgentLogs()

    emit("system", f"All systems online. Agent: GNOSIS | Model: {config['llm_settings']['claude']['model']}", "SYSTEM")
    stats["status"] = "ACTIVE"

    while True:
        try:
            # ── 1. Observe ────────────────────────────────────────
            stats["phase"] = "OBSERVING"
            emit("system", "Initiating observation sweep...", "SYSTEM")
            observation = obs.get()
            log_inst.log_info(str(observation), "bold green", "Observation")

            # ── 2. Memory ─────────────────────────────────────────
            stats["phase"] = "MEMORY"
            memory_ctx = mem.quer_memory()
            log_inst.log_info(str(memory_ctx) or "[empty]", "dim cyan", "Memory")

            # ── 3. Dialog ─────────────────────────────────────────
            stats["phase"] = "DIALOG"
            dialog_ctx = dm.read_dialog()
            log_inst.log_info(str(dialog_ctx), "dim cyan", "Dialog")

            # ── 4. Decide ─────────────────────────────────────────
            stats["phase"] = "DECIDING"
            emit("system", "Consulting the oracle (Claude AI)...", "SYSTEM")
            result = dec.make_decision(observation, memory_ctx, dialog_ctx)
            log_inst.log_info(str(result), "dim magenta", "Decision")
            stats["decisions"] += 1

            # ── 5. Act ────────────────────────────────────────────
            stats["phase"] = "ACTING"
            action.excute(result)
            action_summary = f"{result.get('action','?')} — {str(result.get('content',''))[:120]}"
            emit("action", action_summary, "ACTION")
            stats["actions"] += 1
            stats["last_action"] = action_summary

            # ── 6. Persist dialog ─────────────────────────────────
            dm.write_dialog(result)

            # ── 7. Complete ───────────────────────────────────────
            stats["rounds"] += 1
            stats["phase"] = "DORMANT"
            interval = config.get('interval_time', 300)
            log_inst.log_info(f"Round {stats['rounds']} complete. Next cycle in {interval}s.")
            emit("system", f"Round {stats['rounds']} complete. Dormancy: {interval}s.", "SYSTEM")

        except Exception as e:
            tb = traceback.format_exc()
            emit("error", f"Oracle disruption: {e}", "ERROR")
            emit("error", tb[:400], "TRACE")
            stats["errors"] += 1
            stats["phase"] = "ERROR_RECOVERY"

        time.sleep(config.get('interval_time', 300))

# ── Entry point ───────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
