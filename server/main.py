"""
main.py — Servidor principal del Decibelímetro ISO 8253-1
Uso: python main.py [--port COM3] [--baud 921600]
"""
import asyncio, json, logging, argparse, sys, random, math
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, Response
import uvicorn
from serial_bridge  import SerialBridge
from websocket_hub  import WebSocketHub
import database     as db
from report_generator import generate_pdf

# ── Logging ──────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
log = logging.getLogger("server")

# ── Estado global ─────────────────────────────────────────────
loop:    asyncio.AbstractEventLoop = None
q_in:   asyncio.Queue = None
q_out:  asyncio.Queue = None
bridge: SerialBridge  = None
hub:    WebSocketHub  = None
active_session_id: int = None

# ── Simulación sin hardware ────────────────────────────────────
FALLO_BANDA = "250"
ISO_LIMITS = {"125":35,"250":25,"500":21,"1000":26,"2000":34,"4000":37,"8000":43}

async def demo_loop(q_in: asyncio.Queue):
    t = 0
    log.info("Modo DEMO activo — generando datos simulados cada 400ms")
    while True:
        await asyncio.sleep(0.4)
        t += 1
        bands = {
            "125":  round(28.0 + math.sin(t*0.08)*4   + random.uniform(0, 1.5), 1),
            "250":  round(19.0 + math.sin(t*0.12)*3   + random.uniform(0, 1.5), 1),
            "500":  round(16.0 + math.sin(t*0.07)*2.5 + random.uniform(0, 1.0), 1),
            "1000": round(20.0 + math.sin(t*0.09)*3   + random.uniform(0, 1.5), 1),
            "2000": round(26.0 + math.sin(t*0.06)*3   + random.uniform(0, 1.5), 1),
            "4000": round(29.0 + math.sin(t*0.11)*3   + random.uniform(0, 1.5), 1),
            "8000": round(34.0 + math.sin(t*0.05)*4   + random.uniform(0, 1.5), 1),
        }
        if FALLO_BANDA and t > 37:
            limite = ISO_LIMITS[FALLO_BANDA]
            exceso = min((t - 37) * 0.3, 8.0)
            bands[FALLO_BANDA] = round(limite + exceso + random.uniform(0, 1.5), 1)
        apta = all(bands[k] <= ISO_LIMITS[k] for k in ISO_LIMITS)
        msg = {
            "t":      "meas",
            "ts":     t * 400,
            "spl":    bands,
            "ok":     [bands[str(fc)] <= ISO_LIMITS[str(fc)]
                       for fc in [125, 250, 500, 1000, 2000, 4000, 8000]],
            "apta":   apta,
            "cal_ok": True,
        }
        await q_in.put(msg)

# ── Lifespan ─────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global loop, q_in, q_out, hub, bridge
    loop  = asyncio.get_running_loop()
    q_in  = asyncio.Queue(maxsize=200)
    q_out = asyncio.Queue(maxsize=50)
    hub   = WebSocketHub()
    db.init_db()
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--port", default=None)
    parser.add_argument("--baud", type=int, default=921600)
    args, _ = parser.parse_known_args()
    bridge = SerialBridge(loop, q_in, q_out)
    if args.port:
        if bridge.connect(args.port, args.baud):
            bridge.start()
            log.info(f"ESP32 conectado en {args.port} @ {args.baud}")
        else:
            log.warning("No se pudo abrir el puerto serie. Activando modo demo.")
            asyncio.create_task(demo_loop(q_in))
    else:
        log.warning("Sin --port: modo demo activo (sin hardware ESP32)")
        asyncio.create_task(demo_loop(q_in))
    asyncio.create_task(broadcast_loop())
    yield
    bridge.disconnect()

app = FastAPI(title="Decibelímetro ISO 8253-1", lifespan=lifespan)
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/", response_class=HTMLResponse)
async def root():
    return (static_dir / "index.html").read_text(encoding="utf-8")

# ── Broadcast ────────────────────────────────────────────────
async def broadcast_loop():
    global active_session_id
    while True:
        msg = await q_in.get()
        msg_type = msg.get("t")
        if msg_type == "meas" and active_session_id:
            db.insert_measurement(active_session_id, msg)
        await hub.broadcast(msg)

# ── WebSocket ─────────────────────────────────────────────────
@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    hub.add(websocket)
    try:
        while True:
            text = await websocket.receive_text()
            try:
                cmd = json.loads(text)
                await route_browser_cmd(cmd, websocket)
            except json.JSONDecodeError:
                log.warning(f"JSON inválido del browser: {text[:80]}")
    except WebSocketDisconnect:
        hub.remove(websocket)

def _to_esp_cmd(cmd: dict) -> dict:
    """
    Traduce el formato del browser {"action":"start",...}
    al formato que espera el firmware ESP32 {"cmd":"start",...}
    """
    esp = {k: v for k, v in cmd.items()}
    if "action" in esp and "cmd" not in esp:
        esp["cmd"] = esp.pop("action")
    return esp

async def route_browser_cmd(cmd: dict, ws: WebSocket):
    global active_session_id
    action = cmd.get("action") or cmd.get("cmd")

    if action == "connect_port":
        port = cmd.get("port")
        baud = cmd.get("baud", 921600)
        ok   = bridge.connect(port, baud)
        if ok: bridge.start()
        await ws.send_text(json.dumps({"t":"port_status","ok":ok,"port":port}))

    elif action == "list_ports":
        ports = SerialBridge.list_ports()
        await ws.send_text(json.dumps({"t":"ports","list":ports}))

    elif action == "new_session":
        active_session_id = db.create_session()
        await ws.send_text(json.dumps({"t":"session","id":active_session_id}))

    elif action == "update_session":
        if active_session_id:
            db.update_session(active_session_id, cmd.get("data",{}))
        await ws.send_text(json.dumps({"t":"session_saved"}))

    elif action in ("start","stop","calibrate","status","reset"):
        if action == "start":
            if active_session_id is None:
                active_session_id = db.create_session()
                await ws.send_text(json.dumps({"t":"session","id":active_session_id}))
            await ws.send_text(json.dumps({
                "t":"status","state":"measuring","cal_ok":True,"cal_factor":1.0
            }))
        elif action == "stop":
            await ws.send_text(json.dumps({
                "t":"status","state":"idle","cal_ok":True,"cal_factor":1.0
            }))
        elif action == "calibrate":
            await ws.send_text(json.dumps({
                "t":"cal_done","measured":94.0,"ref":94.0,"factor":1.00000
            }))
        elif action == "status":
            await ws.send_text(json.dumps({
                "t":"status","state":"idle","cal_ok":True,"cal_factor":1.0
            }))
        elif action == "reset":
            log.info("Reset solicitado")

        # ── Reenviar al ESP32 traduciendo "action" → "cmd" ──────
        if bridge and bridge.is_connected:
            esp_cmd = _to_esp_cmd(cmd)
            log.info(f"→ ESP32: {json.dumps(esp_cmd)}")
            bridge.send_cmd(esp_cmd)

    elif action == "finalize":
        apta = cmd.get("apta", False)
        if active_session_id:
            db.finalize_session(active_session_id, apta)
        await ws.send_text(json.dumps({"t":"finalized"}))

    elif action == "list_sessions":
        sessions = db.list_sessions()
        await ws.send_text(json.dumps({"t":"sessions","list":sessions}))

# ── REST ─────────────────────────────────────────────────────
@app.get("/api/ports")
async def api_ports():
    return {"ports": SerialBridge.list_ports()}

@app.get("/api/sessions")
async def api_sessions():
    return {"sessions": db.list_sessions()}

@app.post("/api/session/{sid}/update")
async def api_update_session(sid: int, data: dict):
    db.update_session(sid, data)
    return {"ok": True}

@app.get("/api/report/{session_id}")
async def api_generate_report(session_id: int):
    session  = db.get_session(session_id)
    if not session:
        raise HTTPException(404, "Sesión no encontrada")
    averages = db.get_session_averages(session_id)
    pdf_bytes = generate_pdf(session, averages)
    filename  = f"informe_ISO8253_{session_id:04d}_{session.get('started_at','')[:10]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

# ── Entry point ───────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Servidor Decibelímetro ISO 8253-1")
    parser.add_argument("--port",    default=None)
    parser.add_argument("--baud",    type=int, default=921600)
    parser.add_argument("--host",    default="127.0.0.1")
    parser.add_argument("--webport", type=int, default=8000)
    args = parser.parse_args()
    print(f"\n{'='*55}")
    print(f"  Decibelímetro ISO 8253-1 — UNER 2026")
    print(f"  Servidor: http://{args.host}:{args.webport}")
    print(f"  Puerto ESP32: {args.port or 'no especificado (modo demo)'}")
    if not args.port:
        print(f"  Fallo simulado en banda: {FALLO_BANDA or 'ninguno (todas OK)'}")
    print(f"{'='*55}\n")
    uvicorn.run(
        "main:app",
        host=args.host,
        port=args.webport,
        reload=False,
        log_level="info",
    )
