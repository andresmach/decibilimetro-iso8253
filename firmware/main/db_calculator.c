/* db_calculator.c — dB SPL, ponderación A, verificación ISO 8253-1, calibración */
#include "db_calculator.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "nvs_flash.h"
#include "nvs.h"
#include <math.h>
#include <stdio.h>
#include <string.h>

static const char *TAG = "DB_CALC";

float g_cal_factor = 1.0f;  // Default sin calibrar

/* ── Inicialización: carga factor de calibración desde NVS ─── */
void db_calc_init(void) {
    nvs_handle_t nvs;
    esp_err_t err = nvs_open(NVS_NAMESPACE, NVS_READONLY, &nvs);
    if (err == ESP_OK) {
        uint32_t raw = 0;
        if (nvs_get_u32(nvs, NVS_CAL_KEY, &raw) == ESP_OK) {
            memcpy(&g_cal_factor, &raw, sizeof(float));
            ESP_LOGI(TAG, "Factor de calibración cargado: %.5f", g_cal_factor);
        }
        nvs_close(nvs);
    } else {
        ESP_LOGW(TAG, "NVS sin calibración previa — usando factor = 1.0");
    }
}

/* ── Cálculo de dB SPL a partir de suma de cuadrados ───────── */
float compute_db_spl(float sum_sq, int n_samples) {
    if (n_samples == 0 || sum_sq <= 0.0f) return -120.0f;
    float rms      = sqrtf(sum_sq / (float)n_samples);
    float pressure = rms * g_cal_factor;
    if (pressure < 1e-10f) return -120.0f;
    return 20.0f * log10f(pressure / P_REF);
}

/* ── Ponderación A + verificación ISO ───────────────────────── */
void iso_validate(float db_spl[N_BANDS], MeasurementResult *out) {
    out->cabina_apta  = true;
    out->timestamp_ms = (uint32_t)(esp_timer_get_time() / 1000ULL);
    for (int b = 0; b < N_BANDS; b++) {
        out->db_spl[b] = db_spl[b];
        out->db_a[b]   = db_spl[b] + A_WEIGHT_DB[b];
        out->band_ok[b]= (db_spl[b] <= ISO_LIMITS[b]);
        if (!out->band_ok[b]) out->cabina_apta = false;
    }
}

/* ── Calibración: ajusta factor para que 1kHz = ref_db ─────── */
void calibrate(float measured_db_1k, float ref_db) {
    float error_db    = ref_db - measured_db_1k;
    g_cal_factor     *= powf(10.0f, error_db / 20.0f);
    ESP_LOGI(TAG, "Calibración: medido=%.1f ref=%.1f factor=%.5f",
             measured_db_1k, ref_db, g_cal_factor);
    /* Persistir en NVS */
    nvs_handle_t nvs;
    if (nvs_open(NVS_NAMESPACE, NVS_READWRITE, &nvs) == ESP_OK) {
        uint32_t raw;
        memcpy(&raw, &g_cal_factor, sizeof(float));
        nvs_set_u32(nvs, NVS_CAL_KEY, raw);
        nvs_commit(nvs);
        nvs_close(nvs);
    }
}

/* ── Serializar resultado como JSON (una línea) ─────────────── */
int result_to_json(const MeasurementResult *r, char *buf, int buf_size) {
    return snprintf(buf, buf_size,
        "{\"t\":\"meas\",\"ts\":%lu,"
        "\"spl\":{\"125\":%.1f,\"250\":%.1f,\"500\":%.1f,"
        "\"1000\":%.1f,\"2000\":%.1f,\"4000\":%.1f,\"8000\":%.1f},"
        "\"ok\":[%d,%d,%d,%d,%d,%d,%d],"
        "\"apta\":%s,\"cal_ok\":%s}\n",
        (unsigned long)r->timestamp_ms,
        r->db_spl[0], r->db_spl[1], r->db_spl[2], r->db_spl[3],
        r->db_spl[4], r->db_spl[5], r->db_spl[6],
        r->band_ok[0], r->band_ok[1], r->band_ok[2], r->band_ok[3],
        r->band_ok[4], r->band_ok[5], r->band_ok[6],
        r->cabina_apta ? "true" : "false",
        g_cal_factor != 1.0f ? "true" : "false"
    );
}
