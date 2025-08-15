#ifndef _SPI_H
#define _SPI_H

#ifdef __cplusplus
extern "C"
{
#endif

#define SPI_CS                  (GPIO_NUM_15)   
#define SPI_CLK                 (GPIO_NUM_13)
#define SPI_MISO                (GPIO_NUM_12)
#define SPI_MOSI                (GPIO_NUM_14)
#define SPI_DRDY                (GPIO_NUM_25)

void spi_init(void);
void spi_task(void);

#ifdef __cplusplus
}
#endif
#endif 

