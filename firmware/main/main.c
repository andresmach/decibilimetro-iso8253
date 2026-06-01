/* main.c — Decibelímetro de Bandas de Octava ISO 8253-1
   ESP32 + INMP441 (I2S) + RS-232 → Servidor Python
   Curso DSP — Bioingeniería UNER 2026
   ─────────────────────────────────────────────────────────────
   Arquitectura dual-core:
     Core 0: captura I2S (task_i2s) + recepción UART (uart_rx_task)
     Core 1: procesamiento DSP + envío de resultados (task_dsp)
   ─────────────────────────────────────────────────────────────*/
#include <stdio.h>
#include <string.h>
#include <stdbool.h>
#include <stdint.h>
#include <math.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "freertos/queue.h"

#include "driver/i2s.h"
#include "driver/uart.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "nvs_flash.h"

#include "app_config.h"
#include "biquad_filters.h"
#include "db_calculator.h"
#include "uart_comm.h"

static const char *TAG = "MAIN";

/* ── Buffers compartidos entre tareas ──────────────────────── */
static int32_t s_dma_raw[DMA_BUF_LEN];
static float   s_audio_pool[QUEUE_DEPTH][DMA_BUF_LEN];
static int     s_pool_idx = 0;

static QueueHandle_t     s_audio_queue;
static SemaphoreHandle_t s_data_ready;

/* ── Estado de la FSM ───────────────────────────────────────── */
typedef enum { STATE_IDLE, STATE_CALIBRATING, STATE_MEASURING } AppState;
static volatile AppState s_state   = STATE_IDLE;
static volatile float    s_avg_sec = 30.0f;
static volatile bool     s_cal_ok  = false;

/* ── Tarea I2S: captura audio en Core 0 ─────────────────────── */
static void task_i2s(void *pv)
{
    size_t bytes_read;
    uint32_t log_count = 0;    /* contador para log periódico de diagnóstico */

    ESP_LOGI(TAG, "task_i2s arrancada en Core 0 — esperando datos del INMP441...");

    while (1) {
        /* Lee un bloque DMA — bloqueante hasta que el INMP441 envíe datos */
        esp_err_t ret = i2s_read(I2S_PORT, s_dma_raw,
                                  DMA_BUF_LEN * sizeof(int32_t),
                                  &bytes_read, pdMS_TO_TICKS(1000));

        /* ── DIAGNÓSTICO DE MICRÓFONO ─────────────────────────
         * Si i2s_read hace timeout (ret != ESP_OK o bytes_read == 0)
         * el micrófono no está enviando datos → revisar conexiones.
         * Si bytes_read > 0 pero s_dma_raw[0] == 0 siempre →
         * L/R incorrecto o micrófono defectuoso.
         * ──────────────────────────────────────────────────── */
        if (ret != ESP_OK || bytes_read == 0) {
            ESP_LOGW(TAG, "I2S timeout — INMP441 no responde. "
                          "Verificar: VDD=3.3V, GND, SD=D32, WS=D15, SCK=D14, L/R=GND");
            continue;
        }

        int n = (int)(bytes_read / sizeof(int32_t));

        /* Log de diagnóstico cada 100 bloques (~2 s) */
        log_count++;
        if (log_count % 100 == 1) {
            int32_t mx = s_dma_raw[0];
            for (int i = 1; i < n; i++) {
                if (s_dma_raw[i] > mx) mx = s_dma_raw[i];
            }
            float mx_f = (float)(mx >> 8) / 8388608.0f;
            if (mx == 0) {
                ESP_LOGW(TAG, "I2S OK (%d bytes) pero TODAS las muestras son 0. "
                              "Revisar L/R=GND y soladura de SD (D32).", (int)bytes_read);
            } else {
                ESP_LOGI(TAG, "I2S OK: %d bytes | max_raw=%ld | max_norm=%.4f",
                         (int)bytes_read, (long)mx, mx_f);
            }
        }

        /* Obtiene el siguiente buffer del pool (round-robin) */
        float *dst = s_audio_pool[s_pool_idx % QUEUE_DEPTH];
        s_pool_idx++;

        /* Convierte int32 → float32 normalizado [-1, 1]
         * INMP441/ICS43434: dato de 24 bits justificado a la izquierda
         * en trama de 32 bits → desplazar 8 bits a la derecha */
        for (int i = 0; i < n; i++) {
            dst[i] = (float)(s_dma_raw[i] >> 8) / 8388608.0f;  /* /2^23 */
        }

        /* Envía puntero a la cola sin bloquear */
        if (xQueueSend(s_audio_queue, &dst, 0) != pdTRUE) {
            /* Cola llena: DSP no alcanza — ignorar bloque */
        }
    }
}

/* ── Tarea DSP: filtra y calcula dB SPL en Core 1 ──────────── */
static void task_dsp(void *pv)
{
    float  *blk;
    double  sum_sq[N_BANDS];
    long    n_accum    = 0;
    double  cal_sum_sq = 0.0;
    long    cal_n      = 0;
    int     buf_count  = 0;

    memset(sum_sq, 0, sizeof(sum_sq));

    while (1) {
        /* Esperar un bloque de audio (timeout 500 ms) */
        if (xQueueReceive(s_audio_queue, &blk, pdMS_TO_TICKS(500)) != pdTRUE) {
            if (s_state == STATE_MEASURING) {
                uart_send_status("measuring", s_cal_ok);
            }
            continue;
        }

        if (s_state == STATE_IDLE) {
            /* Sin procesamiento — solo atender comandos al final */
        }
        else if (s_state == STATE_CALIBRATING) {
            for (int i = 0; i < DMA_BUF_LEN; i++) {
                float y = biquad_process(&octave_filters[3], blk[i]);
                cal_sum_sq += (double)(y * y);
            }
            cal_n += DMA_BUF_LEN;

            if (cal_n >= (long)(5.0f * SAMPLE_RATE)) {
                float db_1k = compute_db_spl((float)cal_sum_sq, (int)cal_n);
                calibrate(db_1k, s_avg_sec);
                s_cal_ok = true;

                char buf[128];
                snprintf(buf, sizeof(buf),
                    "{\"t\":\"cal_done\",\"measured\":%.1f,\"ref\":%.1f,\"factor\":%.5f}\n",
                    db_1k, s_avg_sec, g_cal_factor);
                uart_write_bytes(UART_NUM_COMM, buf, (int)strlen(buf));

                biquad_reset_all();
                cal_sum_sq = 0.0;
                cal_n      = 0;
                s_state    = STATE_IDLE;
            }
        }
        else if (s_state == STATE_MEASURING) {
            for (int i = 0; i < DMA_BUF_LEN; i++) {
                float x = blk[i];
                for (int b = 0; b < N_BANDS; b++) {
                    float y = biquad_process(&octave_filters[b], x);
                    sum_sq[b] += (double)(y * y);
                }
            }
            n_accum += DMA_BUF_LEN;
            buf_count++;

            if (buf_count >= MEAS_WINDOW_BUFS) {
                float db[N_BANDS];
                for (int b = 0; b < N_BANDS; b++) {
                    db[b] = compute_db_spl((float)sum_sq[b], (int)n_accum);
                }

                MeasurementResult result;
                iso_validate(db, &result);
                uart_send_result(&result);

                memset(sum_sq, 0, sizeof(sum_sq));
                n_accum   = 0;
                buf_count = 0;
            }
        }

        /* Atender comandos UART (no bloqueante) */
        Command cmd;
        if (uart_recv_cmd(&cmd)) {
            switch (cmd.type) {
                case CMD_START:
                    s_avg_sec = cmd.param_f;
                    biquad_reset_all();
                    memset(sum_sq, 0, sizeof(sum_sq));
                    n_accum   = 0;
                    buf_count = 0;
                    s_state   = STATE_MEASURING;
                    uart_send_status("measuring", s_cal_ok);
                    ESP_LOGI(TAG, "Medicion iniciada — ventana: %.0fs", s_avg_sec);
                    break;

                case CMD_STOP:
                    s_state = STATE_IDLE;
                    uart_send_status("idle", s_cal_ok);
                    break;

                case CMD_CALIBRATE:
                    s_avg_sec  = cmd.param_f;
                    biquad_reset_all();
                    cal_sum_sq = 0.0;
                    cal_n      = 0;
                    s_state    = STATE_CALIBRATING;
                    uart_send_status("calibrating", s_cal_ok);
                    break;

                case CMD_STATUS:
                    uart_send_status(
                        s_state == STATE_MEASURING   ? "measuring"   :
                        s_state == STATE_CALIBRATING ? "calibrating" : "idle",
                        s_cal_ok);
                    break;

                case CMD_RESET:
                    ESP_LOGI(TAG, "Reset solicitado por Python");
                    esp_restart();
                    break;

                default:
                    break;
            }
        }
    }
}

/* ── Configuración I2S para INMP441 / ICS43434 ──────────────── */
static void i2s_init(void)
{
    i2s_config_t cfg = {
        .mode                 = I2S_MODE_MASTER | I2S_MODE_RX,
        .sample_rate          = SAMPLE_RATE,
        .bits_per_sample      = I2S_BITS_PER_SAMPLE_32BIT,
        .channel_format       = I2S_CHANNEL_FMT_ONLY_LEFT,  /* L/R=GND → canal izq */
        .communication_format = I2S_COMM_FORMAT_STAND_I2S,
        .intr_alloc_flags     = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count        = DMA_BUF_COUNT,
        .dma_buf_len          = DMA_BUF_LEN,
        .use_apll             = true,
        .tx_desc_auto_clear   = false,
        .fixed_mclk           = 0,
    };
    i2s_pin_config_t pins = {
        .bck_io_num   = I2S_BCK_PIN,   /* D14 */
        .ws_io_num    = I2S_WS_PIN,    /* D15 */
        .data_in_num  = I2S_DATA_PIN,  /* D32 */
        .data_out_num = I2S_PIN_NO_CHANGE,
    };
    ESP_ERROR_CHECK(i2s_driver_install(I2S_PORT, &cfg, 0, NULL));
    ESP_ERROR_CHECK(i2s_set_pin(I2S_PORT, &pins));
    ESP_LOGI(TAG, "I2S listo: Fs=%d Hz  BCK=D%d  WS=D%d  DATA=D%d",
             SAMPLE_RATE, I2S_BCK_PIN, I2S_WS_PIN, I2S_DATA_PIN);
    ESP_LOGI(TAG, "Conexion esperada: INMP441/ICS43434");
    ESP_LOGI(TAG, "  VDD → 3V3  |  GND → GND  |  L/R → GND");
    ESP_LOGI(TAG, "  SD  → D32  |  WS  → D15  |  SCK → D14");
}

/* ── app_main ───────────────────────────────────────────────── */
void app_main(void)
{
    /* NVS */
    esp_err_t nvs_err = nvs_flash_init();
    if (nvs_err == ESP_ERR_NVS_NO_FREE_PAGES ||
        nvs_err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        nvs_flash_erase();
        nvs_flash_init();
    }

    ESP_LOGI(TAG, "=== Decibel\xc3\xadmetro ISO 8253-1 \xe2\x80\x94 UNER 2026 ===");

    db_calc_init();
    biquad_init_all();
    

uart_comm_init();
esp_log_level_set("*", ESP_LOG_NONE);    /* silenciar logs — UART0 se usa para JSON */

    s_audio_queue = xQueueCreate(QUEUE_DEPTH, sizeof(float *));
    s_data_ready  = xSemaphoreCreateBinary();

    i2s_init();

    xTaskCreatePinnedToCore(task_i2s, "i2s_cap", 4096, NULL, 10, NULL, 0);
    xTaskCreatePinnedToCore(task_dsp, "dsp",     8192, NULL,  9, NULL, 1);

    uart_send_status("idle", g_cal_factor != 1.0f);
    ESP_LOGI(TAG, "Sistema listo. Esperando comandos por RS-232.");

    /*
     * Mantener app_main viva indefinidamente.
     * Sin este bucle FreeRTOS reinicia el sistema cuando
     * app_main retorna (comportamiento observado en los logs).
     */
    while (1) {
        vTaskDelay(pdMS_TO_TICKS(10000));
    }
}