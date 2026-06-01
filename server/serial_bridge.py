"""
serial_bridge.py — Bridge RS-232 ↔ asyncio
Corre en un hilo separado para no bloquear el event loop de FastAPI.
Usa asyncio.Queue como canal thread-safe hacia el WebSocket hub.
"""
import threading
import asyncio
import json
import time
import logging
from typing import Optional
import serial
import serial.tools.list_ports

log = logging.getLogger("serial_bridge")

class SerialBridge:
    def __init__(self, loop: asyncio.AbstractEventLoop,
                 q_in: asyncio.Queue,   # ESP32 → Python → browser
                 q_out: asyncio.Queue): # browser → Python → ESP32
        self.loop    = loop
        self.q_in    = q_in
        self.q_out   = q_out
        self.ser: Optional[serial.Serial] = None
        self.running = False
        self.port    = None
        self._thread: Optional[threading.Thread] = None

    # ── Listar puertos disponibles ───────────────────────────
    @staticmethod
    def list_ports() -> list[str]:
        return [p.device for p in serial.tools.list_ports.comports()]

    # ── Conectar al puerto serie ─────────────────────────────
    def connect(self, port: str, baud: int = 921600) -> bool:
        try:
            self.ser = serial.Serial(
                port, baud,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1,
                rtscts=False,
            )
            self.port = port
            log.info(f"Conectado a {port} @ {baud} bps")
            return True
        except serial.SerialException as e:
            log.error(f"Error abriendo {port}: {e}")
            return False

    def disconnect(self):
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.close()
        log.info("Puerto serie cerrado")

    # ── Iniciar hilo de lectura/escritura ────────────────────
    def start(self):
        self.running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        """Hilo bloqueante: lee líneas del ESP32 y escribe comandos pendientes."""
        buf = b""
        while self.running:
            # ── Leer desde el ESP32 ──────────────────────────
            if self.ser and self.ser.is_open:
                try:
                    chunk = self.ser.read(self.ser.in_waiting or 1)
                    if chunk:
                        buf += chunk
                        while b"\n" in buf:
                            line, buf = buf.split(b"\n", 1)
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                msg = json.loads(line.decode("utf-8", errors="replace"))
                                # Poner en la cola asyncio (thread-safe)
                                asyncio.run_coroutine_threadsafe(
                                    self.q_in.put(msg), self.loop
                                )
                            except json.JSONDecodeError:
                                log.warning(f"Trama inválida: {line[:80]}")
                except serial.SerialException as e:
                    log.error(f"Error de lectura serie: {e}")
                    time.sleep(1)

            # ── Escribir comandos pendientes hacia el ESP32 ──
            try:
                # get_nowait es thread-safe
                cmd = self.q_out.get_nowait()
                if self.ser and self.ser.is_open:
                    payload = (json.dumps(cmd) + "\n").encode("utf-8")
                    self.ser.write(payload)
                    log.debug(f"→ ESP32: {json.dumps(cmd)}")
            except asyncio.QueueEmpty:
                pass
            except Exception as e:
                log.error(f"Error de escritura serie: {e}")

            time.sleep(0.005)   # 5 ms entre iteraciones

    # ── Enviar un comando al ESP32 (thread-safe) ─────────────
    def send_cmd(self, cmd: dict):
        """Puede llamarse desde cualquier hilo o corutina."""
        asyncio.run_coroutine_threadsafe(self.q_out.put(cmd), self.loop)

    @property
    def is_connected(self) -> bool:
        return self.ser is not None and self.ser.is_open
