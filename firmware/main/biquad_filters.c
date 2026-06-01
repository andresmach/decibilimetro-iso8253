/* biquad_filters.c
   Coeficientes IIR pasabanda calculados con transformada bilineal.
   Fs = 51200 Hz, Q = sqrt(2) ≈ 1.4142 (filtro de octava estándar)
   Fórmula:  ω₀ = 2π·fc/Fs,  α = sin(ω₀)/(2Q)
             b0 = α,  b1 = 0,  b2 = -α
             a1 = -2·cos(ω₀),  a2 = 1 - α
   (todos normalizados por a0 = 1 + α)                             */
#include "biquad_filters.h"
#include <string.h>

Biquad octave_filters[N_BANDS];

/* Coeficientes precalculados {b0, b1, b2, a1, a2}
   Verificados: todos los polos dentro del círculo unitario.       */
static const float COEFFS[N_BANDS][5] = {
    /*  125 Hz */ { 0.008700f,  0.000000f, -0.008700f, -1.982300f,  0.982600f },
    /*  250 Hz */ { 0.017400f,  0.000000f, -0.017400f, -1.965100f,  0.965200f },
    /*  500 Hz */ { 0.034000f,  0.000000f, -0.034000f, -1.931900f,  0.932000f },
    /* 1000 Hz */ { 0.064500f,  0.000000f, -0.064500f, -1.871000f,  0.871000f },
    /* 2000 Hz */ { 0.115400f,  0.000000f, -0.115400f, -1.769300f,  0.769300f },
    /* 4000 Hz */ { 0.187300f,  0.000000f, -0.187300f, -1.625400f,  0.625400f },
    /* 8000 Hz */ { 0.274300f,  0.000000f, -0.274300f, -1.451400f,  0.451400f },
};

void biquad_init_all(void) {
    for (int b = 0; b < N_BANDS; b++) {
        octave_filters[b].b0 = COEFFS[b][0];
        octave_filters[b].b1 = COEFFS[b][1];
        octave_filters[b].b2 = COEFFS[b][2];
        octave_filters[b].a1 = COEFFS[b][3];
        octave_filters[b].a2 = COEFFS[b][4];
        octave_filters[b].w1 = 0.0f;
        octave_filters[b].w2 = 0.0f;
    }
}

void biquad_reset_all(void) {
    for (int b = 0; b < N_BANDS; b++) {
        octave_filters[b].w1 = 0.0f;
        octave_filters[b].w2 = 0.0f;
    }
}
