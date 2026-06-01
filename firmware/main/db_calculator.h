#pragma once
/* db_calculator.h — Cálculo dB SPL y verificación ISO 8253-1 */
#include "app_config.h"
#include <stdbool.h>
#include <stdint.h>

/* Resultado de una trama de medición (200 ms) */
typedef struct {
    float    db_spl[N_BANDS];   /* Nivel por banda en dB SPL          */
    float    db_a[N_BANDS];     /* Nivel con ponderación A en dBA      */
    bool     band_ok[N_BANDS];  /* true = cumple ISO 8253-1            */
    bool     cabina_apta;       /* true = TODAS las bandas cumplen     */
    uint32_t timestamp_ms;      /* esp_timer_get_time() / 1000         */
} MeasurementResult;

/* Factor de calibración global — cargado desde NVS al inicio */
extern float g_cal_factor;

/* Inicializa NVS y carga el factor de calibración guardado */
void db_calc_init(void);

/* Computa dB SPL a partir de la suma acumulada de cuadrados y N muestras */
float compute_db_spl(float sum_sq, int n_samples);

/* Aplica ponderación A y verifica ISO — rellena MeasurementResult */
void iso_validate(float db_spl[N_BANDS], MeasurementResult *out);

/* Ajusta g_cal_factor para que la lectura en banda de 1kHz = ref_db */
void calibrate(float measured_db_1k, float ref_db);

/* Serializa MeasurementResult como JSON (1 línea + \n) en buf */
int result_to_json(const MeasurementResult *r, char *buf, int buf_size);
