# 🎙️ Octave-Band Sound Level Meter — ISO 8253-1

**Real-time ambient noise analyzer for audiometric booths**  
ESP32 + INMP441 · FreeRTOS · IEC 61672 Cl.2 · FastAPI · WebSocket

> Developed for the Digital Signal Processing course — Biomedical Engineering, UNER 2026

[![ESP-IDF](https://img.shields.io/badge/ESP--IDF-v5.4-blue)](https://docs.espressif.com/projects/esp-idf/)
[![Python](https://img.shields.io/badge/Python-3.11+-green)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## 📋 Overview

This system measures ambient noise in audiometric booths across **7 octave bands** (125 Hz – 8 kHz) and verifies compliance with **ISO 8253-1:2010** limits in real time. A booth that exceeds any limit invalidates any audiometry performed inside — this tool allows the audiologist to verify the booth before each session, document the measurement, and generate a printable PDF protocol.

### Key Features

- ✅ Real-time 7-band octave analysis updated every **200 ms**
- ✅ **APTA / RUIDO EXCESIVO** verdict per ISO 8253-1:2010
- ✅ Microphone calibration with reference source (94 dB SPL @ 1 kHz)
- ✅ Session history stored in **SQLite**
- ✅ **PDF report** generation per session
- ✅ Demo mode (no hardware required)
- ✅ Web dashboard accessible from any browser on the local network

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      ESP32 DevKit v1                        │
│                                                             │
│  INMP441        Core 0               Core 1                 │
│  (I2S 24-bit)──►task_i2s_capture()──►task_dsp_process()    │
│                  DMA buffer           7× Biquad IIR         │
│                  int32 → float        IEC 61672 Cl.2        │
│                  pool of 4 bufs       RMS → dB SPL          │
│                  FreeRTOS queue       Ponderación A         │
│                                       ISO 8253-1 check      │
│                                            │                │
│                                       UART1 921600 bps      │
│                                       JSON Lines            │
└─────────────────────────────────────────────────────────────┘
                              │
                    USB (jumper D17→RX0)
                              │
┌─────────────────────────────────────────────────────────────┐
│                   Python Server (FastAPI)                   │
│                                                             │
│   SerialBridge ──► asyncio.Queue ──► broadcast_loop        │
│   (pyserial)        producer/consumer    │                  │
│                                          ▼                  │
│   SQLite ◄── db.insert_measurement()   WebSocketHub        │
│   PDF    ◄── generate_pdf()             (all browsers)     │
└─────────────────────────────────────────────────────────────┘
                              │
                         WebSocket
                              │
┌─────────────────────────────────────────────────────────────┐
│              HTML5 Dashboard (localhost:8000)               │
│                                                             │
│   7-band bar chart · APTA/NO APTA · 60s history graph      │
│   Calibration · Session data · PDF download · History tab  │
└─────────────────────────────────────────────────────────────┘
```

---

## 📐 ISO 8253-1:2010 Limits

| Band (Hz) | Max Level (dB SPL) | Clinical Justification |
|-----------|-------------------|------------------------|
| 125       | 35                | Building structure noise |
| 250       | 25                | Critical vowel zone |
| **500**   | **21 ← strictest**| Defines 0 dBHL reference threshold |
| 1000      | 26                | Main audiological reference frequency |
| 2000      | 34                | High-frequency consonants |
| 4000      | 37                | Peak human hearing sensitivity |
| 8000      | 43                | Upper audiometric limit |

> The 500 Hz band has the strictest limit because the audiometric reference threshold 0 dBHL is defined at that frequency. Any noise above 21 dB SPL in that band masks the weakest test tone.

---

## 🔧 Hardware

### Bill of Materials

| Component | Specification | Approx. Cost |
|-----------|--------------|-------------|
| ESP32 DevKit v1 | Dual-core Xtensa 240 MHz, FreeRTOS | USD 5 |
| INMP441 MEMS mic | I2S 24-bit, SNR 61 dB, 60 Hz–15 kHz | USD 4 |
| LDO 3.3V regulator | Clean supply < 50 mVpp ripple | USD 2 |
| 10µF capacitor ×2 | Power supply decoupling | USD 0.10 |
| Dupont wires | Jumper cables | USD 1 |

> **Alternative microphone:** ICS43434 is pin-compatible with INMP441 and offers 4 dB better SNR (65 dB) and flat response up to 20 kHz — recommended for the 8 kHz band.

### Wiring

```
INMP441 / ICS43434          ESP32 DevKit v1
─────────────────           ───────────────
VDD  ──────────────────────► 3V3
GND  ──────────────────────► GND
SD   ──────────────────────► D32  (GPIO32 · I2S Data)
WS   ──────────────────────► D15  (GPIO15 · I2S Word Select)
SCK  ──────────────────────► D14  (GPIO14 · I2S Bit Clock)
L/R  ──────────────────────► GND  (left channel)
```

```
Communication (single USB cable trick)
──────────────────────────────────────
D17 (GPIO17 · UART1 TX) ──► RX0 (GPIO3 · jumper wire)
USB cable ─────────────────► /dev/ttyUSB0 (Linux) or COM3 (Windows)
```

### ESP32 Pin Reference

```
                    ┌──────────┐
               EN  ─┤  ESP32   ├─ 3V3
               VP  ─┤  WROOM  ├─ GND
               VN  ─┤         ├─ D15 ← WS (I2S)
               D34 ─┤         ├─ D2
               D35 ─┤         ├─ D4
   SD (I2S) ► D32  ─┤         ├─ RX2 (GPIO16)
               D33 ─┤         ├─ TX2 (GPIO17) → jumper → RX0
               D25 ─┤         ├─ D5
               D26 ─┤         ├─ D18
               D27 ─┤         ├─ D19
  SCK (I2S) ► D14  ─┤         ├─ D21
               D12 ─┤         ├─ RX0 ← jumper ← D17
               D13 ─┤         ├─ TX0
               GND ─┤         ├─ D22
               VIN ─┤         ├─ D23
                    └──────────┘
```

---

## ⚙️ DSP Implementation

### Sampling Parameters

| Parameter | Value | Justification |
|-----------|-------|---------------|
| I2S sample rate | 51,200 Hz | Covers up to 20 kHz (Nyquist) |
| ADC resolution | 24 bits | ~144 dB theoretical dynamic range |
| DMA buffer | 1,024 samples | ≈ 20 ms per block |
| Queue depth | 4 buffers | ≈ 80 ms maximum latency |
| Measurement window | 10 buffers | ≈ 200 ms per frame |
| Averaging time | 30 s (configurable) | ISO 8253-1 recommends ≥ 10 s |

### Biquad Filter Coefficients (Fs = 51,200 Hz · IEC 61672 Cl.2)

| Band (Hz) | b0 | b1 | b2 | a1 | a2 |
|-----------|----|----|----|----|-----|
| 125  | 0.008700 | 0.000000 | -0.008700 | -1.982300 | 0.982600 |
| 250  | 0.017400 | 0.000000 | -0.017400 | -1.965100 | 0.965200 |
| 500  | 0.034000 | 0.000000 | -0.034000 | -1.931900 | 0.932000 |
| 1000 | 0.064500 | 0.000000 | -0.064500 | -1.871000 | 0.871000 |
| 2000 | 0.115400 | 0.000000 | -0.115400 | -1.769300 | 0.769300 |
| 4000 | 0.187300 | 0.000000 | -0.187300 | -1.625400 | 0.625400 |
| 8000 | 0.274300 | 0.000000 | -0.274300 | -1.451400 | 0.451400 |

### dB SPL Calculation

```
L = 20 × log₁₀(p / p_ref)    where p_ref = 20 µPa
p = rms(filtered_signal) × calibration_factor
```

### A-Weighting Correction

| Band (Hz) | Correction (dB) |
|-----------|----------------|
| 125  | −16.1 |
| 250  | −8.6  |
| 500  | −3.2  |
| 1000 |  0.0  |
| 2000 | +1.2  |
| 4000 | +1.0  |
| 8000 | −1.1  |

---

## 📡 UART Protocol — JSON Lines

**Format:** one JSON object per line, terminated with `\n`. Baud rate: 921,600 bps.

### ESP32 → Python (every 200 ms)

```json
{
  "t": "meas",
  "ts": 1234567,
  "spl": {
    "125": 28.3, "250": 22.1, "500": 18.7,
    "1000": 24.9, "2000": 31.2, "4000": 35.8, "8000": 40.1
  },
  "ok": [1, 1, 1, 1, 1, 1, 1],
  "apta": true,
  "cal_ok": true
}
```

### Python → ESP32 (commands)

```json
{"cmd": "start",     "avg_s": 30}
{"cmd": "stop"}
{"cmd": "calibrate", "ref_db": 94.0}
{"cmd": "status"}
{"cmd": "reset"}
```

### ESP32 FSM States

```
STATE_IDLE ──CMD_START──► STATE_MEASURING ──CMD_STOP──► STATE_IDLE
STATE_IDLE ──CMD_CALIBRATE──► STATE_CALIBRATING ──(5s)──► STATE_IDLE
```

---

## 🚀 Installation & Usage

### 1. Firmware (ESP-IDF v5.4)

```bash
# Install ESP-IDF (if not already installed)
git clone --recursive https://github.com/espressif/esp-idf.git ~/esp/esp-idf
cd ~/esp/esp-idf && ./install.sh esp32

# Build and flash
cd firmware
source ~/esp/esp-idf/export.sh
idf.py build

# Flash (use --no-stub at 57600 if auto-flash fails)
idf.py -p /dev/ttyUSB0 flash

# Monitor (115200 baud)
idf.py -p /dev/ttyUSB0 monitor -b 115200
```

### 2. Server (Python 3.11+)

```bash
cd server
pip install -r requirements.txt

# With ESP32 connected
python3 main.py --port /dev/ttyUSB0

# Demo mode (no hardware)
python3 main.py
```

Open **http://localhost:8000** in any browser.

### 3. Measurement Protocol (ISO 8253-1)

1. Power on and wait **5 minutes** for thermal stabilization
2. Click **CALIBRAR (94 DB)** with the reference source at the microphone
3. Close the audiometric booth under real operating conditions
4. Click **▶ INICIAR** and wait 30 seconds
5. Verify all 7 bands are below ISO limits
6. Click **📄 GENERAR PDF** and attach to the audiological protocol
7. If any band fails: **do not perform audiometry** until the noise source is corrected

---

## 📁 Project Structure

```
decibilimetro-iso8253/
├── firmware/                     ← ESP-IDF project
│   ├── CMakeLists.txt
│   ├── sdkconfig.defaults
│   └── main/
│       ├── main.c               ← app_main + FreeRTOS tasks
│       ├── app_config.h         ← pins, sample rate, constants
│       ├── biquad_filters.c/h   ← 7 IIR Biquad filters (IEC 61672)
│       ├── db_calculator.c/h    ← dB SPL, calibration, A-weighting
│       ├── uart_comm.c/h        ← JSON Lines RS-232 protocol
│       └── cJSON.c/h            ← embedded JSON parser
├── server/                       ← Python server
│   ├── main.py                  ← FastAPI + uvicorn entry point
│   ├── serial_bridge.py         ← RS-232 ↔ asyncio.Queue bridge
│   ├── websocket_hub.py         ← broadcast to all browsers
│   ├── database.py              ← SQLite: sessions + measurements
│   ├── report_generator.py      ← PDF with ReportLab
│   ├── requirements.txt
│   └── static/
│       └── index.html           ← HTML5 dashboard (WebSocket)
├── .gitignore
└── README.md
```

---

## 🧪 Testing Without Audiometric Booth

Generate test tones from the terminal and observe the dashboard response:

```bash
# Install sox
sudo apt install sox

# Low frequency test (125 Hz band should rise)
play -n synth 3 sine 125 vol 0.3

# Mid frequency test (1000 Hz band should rise)
play -n synth 3 sine 1000 vol 0.3

# High frequency test (8000 Hz band should rise)
play -n synth 3 sine 8000 vol 0.3

# Sweep all bands
for f in 125 250 500 1000 2000 4000 8000; do
  echo "Playing $f Hz..."
  play -n synth 2 sine $f vol 0.5
  sleep 0.5
done
```

---

## ⚠️ Limitations

| Limitation | Detail |
|-----------|--------|
| INMP441 response | Documented up to 15 kHz; 8 kHz band is near the sensor's precision limit |
| Absolute calibration | Requires a traceable source (pistonphone to INTI/NIST); a phone app is indicative only |
| Float32 precision | ESP32 uses 32-bit floats (~10⁻⁷ relative error in dB calculations) |
| Legacy I2S API | Uses deprecated ESP-IDF I2S driver (generates warnings); functional but should migrate to `driver/i2s_std.h` |
| Single USB cable | Uses D17→RX0 jumper wire; JSON and debug share UART0 |

---

## 🔮 Future Work

- [ ] Migrate I2S to `driver/i2s_std.h` (ESP-IDF v5.x new API)
- [ ] Replace INMP441 with calibrated measurement microphone (ICS-40300 with NIST certificate)
- [ ] Implement one-third octave bands (21 bands) for higher spectral resolution
- [ ] Add SD card for continuous 24-hour recording
- [ ] MQTT integration for hospital monitoring platforms
- [ ] WiFi mode (eliminate USB cable entirely)

---

## 📚 References

- ISO 8253-1:2010 — *Acoustics: Audiometric test methods. Part 1: Pure-tone air and bone conduction audiometry*
- IEC 61672-1:2013 — *Electroacoustics: Sound level meters. Part 1: Specifications*
- Espressif Systems — *ESP-IDF Programming Guide v5.4*
- InvenSense — *INMP441 Omnidirectional Microphone Datasheet*

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🎓 Course Information

| Field | Value |
|-------|-------|
| Course | Procesamiento Digital de Señales |
| Career | Ingeniería en Bioingeniería |
| Institution | Universidad Nacional de Entre Ríos (UNER) |
| Year | 2026 |
| Hardware | ESP32 DevKit v1 + INMP441 |
| Standard | ISO 8253-1:2010 + IEC 61672-1 Cl.2 |
