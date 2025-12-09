#ifndef _SPI_H
#define _SPI_H

#ifdef __cplusplus
extern "C"
{
#endif

#define SPI_RX_BUF_SIZE    4096         // SPI接收缓冲区大小
#define SPI_TEMP_BUF_SIZE  2048        // SPI临时读取缓冲区大小

#define SPI_CS                  (GPIO_NUM_45)   
#define SPI_CLK                 (GPIO_NUM_48)
#define SPI_MISO                (GPIO_NUM_47)
#define SPI_MOSI                (GPIO_NUM_21)
#define SPI_DRDY                (GPIO_NUM_12)

void spi_init(void);
void spi_task(void);

#ifdef __cplusplus
}
#endif
#endif 

