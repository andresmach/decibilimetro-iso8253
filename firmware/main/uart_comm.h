#pragma once
/* uart_comm.h — Comunicación RS-232 bidireccional con el servidor Python */
#include "app_config.h"
#include "db_calculator.h"
#include <stdbool.h>

/* Tipos de comandos recibidos desde Python */
typedef enum {
    CMD_NONE = 0,
    CMD_START,       // {"cmd":"start","avg_s":N}
    CMD_STOP,        // {"cmd":"stop"}
    CMD_CALIBRATE,   // {"cmd":"calibrate","ref_db":94.0}
    CMD_STATUS,      // {"cmd":"status"}
    CMD_RESET,       // {"cmd":"reset"}
} CmdType;

typedef struct {
    CmdType type;
    float   param_f;    // avg_s o ref_db según el comando
} Command;

/* Inicializa la UART RS-232 y arranca la tarea de recepción */
void uart_comm_init(void);

/* Envía una MeasurementResult serializada como JSON por RS-232 */
void uart_send_result(const MeasurementResult *r);

/* Envía un JSON de estado {"t":"status",...} */
void uart_send_status(const char *state, bool cal_ok);

/* Envía un mensaje de error */
void uart_send_error(const char *code, const char *msg);

/* Intenta leer un comando pendiente (no bloqueante).
   Retorna true si hay un comando nuevo en *cmd. */
bool uart_recv_cmd(Command *cmd);
