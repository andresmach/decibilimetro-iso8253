/* uart_comm.c — RS-232 bidireccional, protocolo JSON Lines */
#include "uart_comm.h"
#include "driver/uart.h"
#include "esp_log.h"
#include "cJSON.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include <string.h>
#include <stdio.h>

static const char *TAG = "UART";

/* Cola interna de comandos recibidos */
static QueueHandle_t s_cmd_queue;
static char s_tx_buf[512];
static char s_rx_line[512];
static int  s_rx_idx = 0;

/* ── Tarea de recepción (corre en background) ───────────────── */
static void uart_rx_task(void *pv) {
    uint8_t byte;
    while (1) {
        int n = uart_read_bytes(UART_NUM_COMM, &byte, 1, pdMS_TO_TICKS(10));
        if (n <= 0) continue;

        if (byte == '\n' || s_rx_idx >= (int)sizeof(s_rx_line)-1) {
            s_rx_line[s_rx_idx] = '\0';
            s_rx_idx = 0;
            if (strlen(s_rx_line) < 5) continue;  // ignorar líneas vacías

            cJSON *root = cJSON_Parse(s_rx_line);
            if (!root) {
                ESP_LOGW(TAG, "JSON inválido: %s", s_rx_line);
                continue;
            }

            Command cmd = {.type = CMD_NONE, .param_f = 0.0f};
            cJSON *jcmd = cJSON_GetObjectItem(root, "cmd");
            if (jcmd && cJSON_IsString(jcmd)) {
                const char *cs = jcmd->valuestring;
                if      (strcmp(cs, "start")     == 0) {
                    cmd.type    = CMD_START;
                    cJSON *js   = cJSON_GetObjectItem(root, "avg_s");
                    cmd.param_f = js ? (float)js->valuedouble : 30.0f;
                }
                else if (strcmp(cs, "stop")      == 0) cmd.type = CMD_STOP;
                else if (strcmp(cs, "calibrate") == 0) {
                    cmd.type    = CMD_CALIBRATE;
                    cJSON *jr   = cJSON_GetObjectItem(root, "ref_db");
                    cmd.param_f = jr ? (float)jr->valuedouble : CAL_REF_DB;
                }
                else if (strcmp(cs, "status")    == 0) cmd.type = CMD_STATUS;
                else if (strcmp(cs, "reset")     == 0) cmd.type = CMD_RESET;
            }
            cJSON_Delete(root);

            if (cmd.type != CMD_NONE)
                xQueueSend(s_cmd_queue, &cmd, 0);
        } else {
            s_rx_line[s_rx_idx++] = (char)byte;
        }
    }
}

/* ── Inicialización ─────────────────────────────────────────── */
void uart_comm_init(void) {
    s_cmd_queue = xQueueCreate(8, sizeof(Command));

    uart_config_t cfg = {
        .baud_rate  = UART_BAUD,
        .data_bits  = UART_DATA_8_BITS,
        .parity     = UART_PARITY_DISABLE,
        .stop_bits  = UART_STOP_BITS_1,
        .flow_ctrl  = UART_HW_FLOWCTRL_DISABLE,   // sin HW flow en primer prototipo
        .source_clk = UART_SCLK_DEFAULT,
    };
    uart_param_config(UART_NUM_COMM, &cfg);
    uart_set_pin(UART_NUM_COMM, UART_TX_PIN, UART_RX_PIN,
                 UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE);
    uart_driver_install(UART_NUM_COMM, UART_BUF_SIZE * 2, UART_BUF_SIZE, 0, NULL, 0);

    xTaskCreatePinnedToCore(uart_rx_task, "uart_rx", 4096, NULL, 5, NULL, 0);
    ESP_LOGI(TAG, "UART1 listo: %d bps TX=%d RX=%d", UART_BAUD, UART_TX_PIN, UART_RX_PIN);
}

/* ── Envío de medición ──────────────────────────────────────── */
void uart_send_result(const MeasurementResult *r) {
    int n = result_to_json(r, s_tx_buf, sizeof(s_tx_buf));
    if (n > 0) uart_write_bytes(UART_NUM_COMM, s_tx_buf, n);
}

/* ── Envío de estado ────────────────────────────────────────── */
void uart_send_status(const char *state, bool cal_ok) {
    int n = snprintf(s_tx_buf, sizeof(s_tx_buf),
        "{\"t\":\"status\",\"state\":\"%s\",\"cal_ok\":%s,\"cal_factor\":%.5f}\n",
        state, cal_ok ? "true" : "false", g_cal_factor);
    if (n > 0) uart_write_bytes(UART_NUM_COMM, s_tx_buf, n);
}

/* ── Envío de error ─────────────────────────────────────────── */
void uart_send_error(const char *code, const char *msg) {
    int n = snprintf(s_tx_buf, sizeof(s_tx_buf),
        "{\"t\":\"err\",\"code\":\"%s\",\"msg\":\"%s\"}\n", code, msg);
    if (n > 0) uart_write_bytes(UART_NUM_COMM, s_tx_buf, n);
}

/* ── Lectura de comando (no bloqueante) ─────────────────────── */
bool uart_recv_cmd(Command *cmd) {
    return xQueueReceive(s_cmd_queue, cmd, 0) == pdTRUE;
}
