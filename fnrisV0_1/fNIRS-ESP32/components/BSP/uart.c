#include <stdio.h>
#include "uart.h"
#include "driver/uart.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "sdkconfig.h"

#include "udp.h"
#include "circular_buffer.h"

#define RX_BUF_SIZE 1024

static const char* TAG = "UART";
static circular_buffer_t uart_rx_buffer;
static uint8_t uart_rx_buf_memory[UART_RX_BUF_SIZE];



/**
 * @brief 初始化UART接收缓冲区
 * @return 操作结果
 */
static bool init_uart_rx_buffer(void)
{
    circ_buf_result_t result = circular_buffer_init_static(&uart_rx_buffer, 
                                                          uart_rx_buf_memory, 
                                                          UART_RX_BUF_SIZE);
    
    if (result != CIRC_BUF_OK) {
        ESP_LOGE(TAG, "Failed to initialize circular buffer: %s", 
                 circular_buffer_get_error_string(result));
        return false;
    }
    
    ESP_LOGI(TAG, "UART RX circular buffer initialized, size: %d bytes", UART_RX_BUF_SIZE);
    return true;
}

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
    uint8_t temp_buf[UART_TEMP_BUF_SIZE];  // 临时接收缓冲区
    int rx_bytes = 0;
    
    ESP_LOGI(TAG, "UART RX task starting...");
    
    // 初始化循环缓冲区
    if (!init_uart_rx_buffer()) {
        ESP_LOGE(TAG, "Failed to initialize UART RX buffer, task exiting");
        vTaskDelete(NULL);
        return;
    }
    
    ESP_LOGI(TAG, "UART RX task started successfully");
    
    while (1) {
        // 从UART读取数据到临时缓冲区
        rx_bytes = uart_read_bytes(UART_NUM, temp_buf, sizeof(temp_buf), 50 / portTICK_PERIOD_MS);
        
        if (rx_bytes > 0) {
            // 将接收到的数据写入循环缓冲区
            int32_t written = circular_buffer_write_force(&uart_rx_buffer, temp_buf, rx_bytes);
            
            if (written < 0) {
                ESP_LOGE(TAG, "Failed to write to circular buffer: %s", 
                         circular_buffer_get_error_string(-written));
                continue;
            }
            
            if (written != rx_bytes) {
                ESP_LOGW(TAG, "Partial write: %d/%d bytes", written, rx_bytes);
            }
            
            // 处理缓冲区中的所有完整帧
            process_all_frames(&uart_rx_buffer);
        }
        
        // 定期检查缓冲区状态（可选的调试信息）
        static uint32_t debug_counter = 0;
        if (++debug_counter % 1000 == 0) {
            int32_t data_len = circular_buffer_get_data_len(&uart_rx_buffer);
            int32_t free_space = circular_buffer_get_free_space(&uart_rx_buffer);
            ESP_LOGD(TAG, "Buffer status: %d bytes used, %d bytes free", data_len, free_space);
        }
        
        // 短暂延时，避免CPU占用过高
        vTaskDelay(10 / portTICK_PERIOD_MS);
    }
    
    // 清理资源（实际上不会执行到这里）
    circular_buffer_deinit(&uart_rx_buffer);
    vTaskDelete(NULL);
}

/**
 * @brief 获取UART接收缓冲区状态信息
 * @param data_len 返回当前数据长度
 * @param free_space 返回剩余空间
 * @return 操作结果
 */
bool uart_rx_get_buffer_status(uint32_t *data_len, uint32_t *free_space)
{
    if (data_len == NULL || free_space == NULL) {
        return false;
    }
    
    int32_t len = circular_buffer_get_data_len(&uart_rx_buffer);
    int32_t free = circular_buffer_get_free_space(&uart_rx_buffer);
    
    if (len < 0 || free < 0) {
        return false;
    }
    
    *data_len = (uint32_t)len;
    *free_space = (uint32_t)free;
    
    return true;
}

/**
 * @brief 重置UART接收缓冲区
 * @return 操作结果
 */
bool uart_rx_reset_buffer(void)
{
    circ_buf_result_t result = circular_buffer_reset(&uart_rx_buffer);
    if (result == CIRC_BUF_OK) {
        ESP_LOGI(TAG, "UART RX buffer reset successfully");
        return true;
    } else {
        ESP_LOGE(TAG, "Failed to reset UART RX buffer: %s", 
                 circular_buffer_get_error_string(result));
        return false;
    }
}

void uart_task(void){
    ESP_LOGE(TAG, "CREATE UART RX");
    xTaskCreate(uart_rx_task, "uart_rx_task", 4096, NULL, 5, NULL);
}

