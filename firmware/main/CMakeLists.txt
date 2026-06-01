idf_component_register(
    SRCS
        "main.c"
        "biquad_filters.c"
        "db_calculator.c"
        "uart_comm.c"
        "cJSON.c"
    INCLUDE_DIRS "."
    REQUIRES
        driver
        esp_timer
        nvs_flash
        freertos
        esp_system
)
