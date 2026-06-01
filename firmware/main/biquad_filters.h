#pragma once
/* biquad_filters.h — Filtros IIR Biquad por banda de octava (IEC 61672 Cl.2) */
#include "app_config.h"
#include <stdint.h>

/* Coeficientes + estado de un filtro biquad.
   Forma directa II transpuesta (más estable numéricamente con float32).
   H(z) = (b0 + b1·z⁻¹ + b2·z⁻²) / (1 + a1·z⁻¹ + a2·z⁻²)             */
typedef struct {
    float b0, b1, b2;   // Coeficientes del numerador
    float a1, a2;       // Coeficientes del denominador (a0 = 1 normalizado)
    float w1, w2;       // Estado interno (historia del filtro)
} Biquad;

/* Array global de 7 filtros (uno por banda de octava) */
extern Biquad octave_filters[N_BANDS];

/* Inicializa los 7 filtros con coeficientes calculados para Fs=51200 Hz */
void biquad_init_all(void);

/* Aplica un filtro biquad a UNA muestra — versión inline para tiempo real */
static inline float biquad_process(Biquad *f, float x) {
    float y = f->b0 * x + f->w1;
    f->w1   = f->b1 * x - f->a1 * y + f->w2;
    f->w2   = f->b2 * x - f->a2 * y;
    return y;
}

/* Resetea el estado interno de todos los filtros (para nueva sesión) */
void biquad_reset_all(void);
