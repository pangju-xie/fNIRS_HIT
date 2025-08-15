#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "esp_log.h"
#include "nvs_flash.h"

#include "led.h"
#include "uart.h"
#include "wifi.h"
#include "spi.h"
#include "udp.h"
#include "transmit.h"

static const char* TAG = "MAIN";
void nvs_init(void){
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    ESP_ERROR_CHECK(err);
}



void app_main(void)
{
    nvs_init();
    led_init();
    Key_init();
    uart_init();
    spi_init();
    command_init();
    int sta = wifi_init();
    ESP_LOGE(TAG, "INIT DONE.");

    if(sta){
        udp_task();
        spi_task();
        uart_task();
    }
    else{
        led_toggle();
        vTaskDelay(100/portTICK_PERIOD_MS);
    }

}
