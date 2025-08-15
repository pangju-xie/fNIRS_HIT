#include <stdio.h>
#include "uart.h"
#include "driver/uart.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "sdkconfig.h"
#include "esp_log.h"

#include "udp.h"


#define RX_BUF_SIZE 1024

static const char* TAG = "UART";

//串口模块初始化
void uart_init(void) {
    const uart_config_t uart_config = {
        .baud_rate = 1000000,                        //波特率设置为921600，通讯速度越快，粘包问题越小
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };
    // We won't use a buffer for sending data.
    uart_driver_install(UART_NUM, RX_BUF_SIZE * 2, 0, 0, NULL, 0);
    uart_param_config(UART_NUM, &uart_config);
    uart_set_pin(UART_NUM, TXD_PIN, RXD_PIN, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE);

    ESP_LOGI(TAG, "UART_INIT_OK!");
}

//串口发送
void uart_tx_task(uint8_t *data, int len){
    int tx_byte = uart_write_bytes(UART_NUM, data, len);
    ESP_LOGI(TAG, "SEND %d bytes UART DATA TO STM32.", tx_byte);
    
    return;
}

//串口接收任务
static void uart_rx_task(void *arg){
    int rxByte = 0;
    uint8_t rxbuf[1000];

    while(1){
        rxByte = uart_read_bytes(UART_NUM, rxbuf, 100, 100/portTICK_PERIOD_MS);
        if(rxByte >= 11){
            ESP_LOGI(TAG, "read %d bytes.", rxByte);
            printf("READ DATA: ");
            for(int i = 0;i<rxByte;i++){
                printf("%02X ", rxbuf[i]);
            }
            printf(".\r\n");
            if(rxbuf[0] == 0xBA && rxbuf[1] == 0xBA && ((uint16_t)rxByte-11 == (uint16_t)((rxbuf[7]<<8)|(rxbuf[8]<<0)))){
                rxbuf[rxByte] = 0;
                udp_safe_send(rxbuf, rxByte);
            }
            else{
                ESP_LOGE(TAG, "wrong pack");
            }
        }
        else if(rxByte>0){
            ESP_LOGE(TAG, "wrong pack");
        }
        vTaskDelay(10/portTICK_PERIOD_MS);
    }
    vTaskDelete(NULL);
}

void uart_task(void){
    ESP_LOGE(TAG, "CREATE UART RX");
    xTaskCreate(uart_rx_task, "uart_rx_task", 4096, NULL, 5, NULL);
}

