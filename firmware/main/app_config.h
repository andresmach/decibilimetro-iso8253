#pragma once
/* ============================================================
   app_config.h  —  Configuración global del sistema
   Decibelímetro de Bandas de Octava — ISO 8253-1
   ESP32 + INMP441   Curso DSP UNER 2026
   ============================================================ */

/* ── I2S / INMP441 ─────────────────────────────────────────── */

#define QUEUE_DEPTH    4
#define I2S_PORT            I2S_NUM_0
#define I2S_BCK_PIN         14          // Bit Clock
#define I2S_WS_PIN          15          // Word Select (LRCK)
#define I2S_DATA_PIN        32          // Serial Data (SD)
#define SAMPLE_RATE         51200       // Hz — Nyquist > 20 kHz
#define DMA_BUF_LEN         1024        // muestras por buffer DMA
#define DMA_BUF_COUNT       8           // buffers DMA en cadena

/* ── DSP ───────────────────────────────────────────────────── */
#define N_BANDS             7           // bandas de octava
#define MEAS_WINDOW_BUFS    10          // 10×1024/51200 ≈ 200 ms por trama
// Para promediado largo (30 s): Python acumula N tramas

/* ── UART RS-232 ───────────────────────────────────────────── */
#define UART_NUM_COMM       UART_NUM_1
#define UART_TX_PIN         17
#define UART_RX_PIN         16
#define UART_RTS_PIN        18          // RTS para control de flujo HW
#define UART_CTS_PIN        19          // CTS
#define UART_BAUD           921600
#define UART_BUF_SIZE       1024



/* ── CALIBRACIÓN ───────────────────────────────────────────── */
#define P_REF               0.00002f    // 20 µPa = presión de referencia acústica
#define CAL_REF_DB          94.0f       // dB SPL del pistonófono
#define NVS_CAL_KEY         "cal_factor"
#define NVS_NAMESPACE       "decibel"

/* ── LÍMITES ISO 8253-1 ────────────────────────────────────── */
// { 125, 250, 500, 1000, 2000, 4000, 8000 } Hz
static const float ISO_LIMITS[N_BANDS] = {35.0f, 25.0f, 21.0f, 26.0f, 34.0f, 37.0f, 43.0f};

/* ── PONDERACIÓN A (IEC 61672) ─────────────────────────────── */
static const float A_WEIGHT_DB[N_BANDS] = {-16.1f, -8.6f, -3.2f, 0.0f, +1.2f, +1.0f, -1.1f};

/* ── FRECUENCIAS CENTRALES ─────────────────────────────────── */
static const int BAND_FC[N_BANDS] = {125, 250, 500, 1000, 2000, 4000, 8000};
