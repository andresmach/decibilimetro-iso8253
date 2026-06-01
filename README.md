# Decibelímetro ISO 8253-1 — UNER 2026
Analizador de ruido para cabinas audiométricas.
ESP32 + INMP441 (I2S) → RS-232 → Python FastAPI → Dashboard HTML5

## Hardware
- ESP32 DevKit v1
- Micrófono INMP441 (I2S 24-bit)
- Conexión: SD=D32, WS=D15, SCK=D14, L/R=GND

## Uso
```bash
cd server
pip install -r requirements.txt
python3 main.py --port /dev/ttyUSB0
```
Abrir http://localhost:8000
