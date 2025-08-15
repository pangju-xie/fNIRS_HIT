#include <stdio.h>
#include <string.h>
#include "driver/spi_slave.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "spi.h"
#include "udp.h"

static const char* TAG = "SPI";

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

    ret=spi_slave_initialize(HSPI_HOST, &buscfg, &slvcfg, SPI_DMA_CH_AUTO);
    assert(ret==ESP_OK);
    ESP_LOGI(TAG, "SPI SLAVE INIT DONE.");
    vTaskDelay(1000/portTICK_PERIOD_MS);
}

/// @brief SPI从机，接收STM32发来的数据
/// @param arg 
static void spi_slave_task(void *arg) {
    spi_slave_transaction_t t;
    memset(&t, 0, sizeof(t));
    uint8_t* rx_buffer = (uint8_t*)malloc(1024); //SPI接收数组
    t.length = 1024 * 8; // 1290 bytes
    t.tx_buffer = NULL;
    t.rx_buffer = rx_buffer;

    while (1) {
        // ESP_LOGI(TAG, "Enfsddgf");
        // Wait for the master to initiate a transfer
        esp_err_t ret = spi_slave_transmit(HSPI_HOST, &t, portMAX_DELAY);
        // if(udpRxData[0] != 0x00)
        //     ESP_LOGI(TAG, "I sent it%x\t%x\t%x.............................................",udpRxData[0],udpRxData[1],udpRxData[2]);
        // ESP_LOGI(TAG, "After  Enfsddgf..............................................");
        if (ret == ESP_OK){
            ESP_LOGI(TAG, "read %d bytes.", t.trans_len/8);
            printf("READ DATA: ");
            for(int i = 0;i<t.trans_len/8;i++){
                printf("%02X ", rx_buffer[i]);
            }
            printf(".\r\n");
            if(rx_buffer[0] == 0xBA && rx_buffer[1] == 0xBA) {    //SPI接收成功且包头有效
                int length = 11+ (int)(rx_buffer[7]<<8|rx_buffer[8]);
                // Data received, send it over UDP
                // ESP_LOGI(TAG, "SPI Data recv ok");
                udp_safe_send(rx_buffer, length);  //将接收到的数据通过WiFi发送给PC
            }
        } else {
            ESP_LOGE(TAG, "SPI slave error occurred: %s", esp_err_to_name(ret));
        }
        vTaskDelay(1/portTICK_PERIOD_MS);
    }

    free(rx_buffer);
    vTaskDelete(NULL);
}

void spi_task(void){
    ESP_LOGE(TAG, "CREATE SPI SLAVE TASK.");
    xTaskCreate(spi_slave_task, "spi_slave", 4096, NULL, 4, NULL);
}
