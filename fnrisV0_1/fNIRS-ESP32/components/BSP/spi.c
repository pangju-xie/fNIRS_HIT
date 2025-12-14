#include <stdio.h>
#include <string.h>
#include "driver/spi_slave.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "spi.h"
// #include "udp.h"
#include "circular_buffer.h"

static const char* TAG = "SPI";
#define SPI_RX_BUF_SIZE 4096
static circular_buffer_t spi_rx_buffer;
static uint8_t spi_rx_buf_memory[SPI_RX_BUF_SIZE];


//Called after a transaction is queued and ready for pickup by master. We use this to set the handshake line high.
void my_post_setup_cb(spi_slave_transaction_t *trans) {
    gpio_set_level(SPI_DRDY, 1);
}

//Called after transaction is sent/received. We use this to set the handshake line low.
void my_post_trans_cb(spi_slave_transaction_t *trans) {
    gpio_set_level(SPI_DRDY, 0);
}

void spi_init(void){
    esp_err_t ret;
    spi_bus_config_t buscfg={
        .mosi_io_num=SPI_MOSI,
        .miso_io_num=SPI_MISO,
        .sclk_io_num=SPI_CLK,
        .quadwp_io_num = -1,
        .quadhd_io_num = -1,
    };
    spi_slave_interface_config_t slvcfg={
        .mode=0,
        .spics_io_num=SPI_CS,
        .queue_size=3,
        .flags=0,
        .post_setup_cb=my_post_setup_cb,
        .post_trans_cb=my_post_trans_cb
    };

    gpio_config_t io_conf={
        .intr_type=GPIO_INTR_DISABLE,
        .mode=GPIO_MODE_OUTPUT,
        .pin_bit_mask=((uint64_t)1<<SPI_DRDY)
    };

        //Configure handshake line as output
    gpio_config(&io_conf);

    //Enable pull-ups on SPI lines so we don't detect rogue pulses when no master is connected.
    gpio_set_pull_mode(SPI_MOSI, GPIO_PULLUP_ONLY);
    gpio_set_pull_mode(SPI_CLK, GPIO_PULLUP_ONLY);
    gpio_set_pull_mode(SPI_CS, GPIO_PULLUP_ONLY);

    ret=spi_slave_initialize(SPI3_HOST, &buscfg, &slvcfg, SPI_DMA_CH_AUTO);
    assert(ret==ESP_OK);
    ESP_LOGI(TAG, "SPI SLAVE INIT DONE.");
    vTaskDelay(1000/portTICK_PERIOD_MS);
}

/**
 * @brief 初始化UART接收缓冲区
 * @return 操作结果
 */
static bool init_spi_rx_buffer(void)
{
    circ_buf_result_t result = circular_buffer_init_static(&spi_rx_buffer, 
                                                          spi_rx_buf_memory, 
                                                          SPI_RX_BUF_SIZE);
    
    if (result != CIRC_BUF_OK) {
        ESP_LOGE(TAG, "Failed to initialize circular buffer: %s", 
                 circular_buffer_get_error_string(result));
        return false;
    }
    
    ESP_LOGI(TAG, "SPI RX circular buffer initialized, size: %d bytes", SPI_RX_BUF_SIZE);
    return true;
}


/// @brief SPI从机，接收STM32发来的数据
/// @param arg 
static void spi_slave_task(void *arg) {
    spi_slave_transaction_t t;
    memset(&t, 0, sizeof(t));
    //uint8_t temp_buf[SPI_TEMP_BUF_SIZE];  // 临时接收缓冲区
    uint8_t* rx_buffer = (uint8_t*)malloc(1024); //SPI接收数组
    t.length = 1024 * 8; // 1290 bytes
    t.tx_buffer = NULL;
    t.rx_buffer = rx_buffer;

    // 初始化循环缓冲区
    if (!init_spi_rx_buffer()) {
        ESP_LOGE(TAG, "Failed to initialize SPI RX buffer, task exiting");
        vTaskDelete(NULL);
        return;
    }
    
    ESP_LOGI(TAG, "SPI RX task started successfully");

    while (1) {
        // Wait for the master to initiate a transfer
        esp_err_t ret = spi_slave_transmit(SPI3_HOST, &t, portMAX_DELAY);
        if(ret == ESP_OK){
            int rx_bytes = t.trans_len/8;
            printf(TAG, "Received %d bytes from STM32", rx_bytes);
            for(int i=rx_bytes-6;i<rx_bytes;i++){
                printf( "0x%02X ", rx_buffer[i]);
            }
            printf("\r\n");
            // 将接收到的数据写入循环缓冲区
            int written = circular_buffer_write_force(&spi_rx_buffer, rx_buffer, rx_bytes);
            
            if (written < 0) {
                ESP_LOGE(TAG, "Failed to write to circular buffer: %s", 
                         circular_buffer_get_error_string(-written));
                continue;
            }
            
            if (written != rx_bytes) {
                ESP_LOGW(TAG, "Partial write: %d/%d bytes", written, rx_bytes);
            }
            
            // 处理缓冲区中的所有完整帧
            process_all_frames(&spi_rx_buffer);
        }
        
        // 定期检查缓冲区状态（可选的调试信息）
        static uint32_t debug_counter = 0;
        if (++debug_counter % 1000 == 0) {
            int data_len = circular_buffer_get_data_len(&spi_rx_buffer);
            int free_space = circular_buffer_get_free_space(&spi_rx_buffer);
            ESP_LOGD(TAG, "Buffer status: %d bytes used, %d bytes free", data_len, free_space);
        }
        
        // 短暂延时，避免CPU占用过高
        vTaskDelay(10 / portTICK_PERIOD_MS);
    }
    
    // 清理资源（实际上不会执行到这里）
    circular_buffer_deinit(&spi_rx_buffer);
    vTaskDelete(NULL);
}

void spi_task(void){
    ESP_LOGE(TAG, "CREATE SPI SLAVE TASK.");
    xTaskCreate(spi_slave_task, "spi_slave", 8192, NULL, 4, NULL);
}
