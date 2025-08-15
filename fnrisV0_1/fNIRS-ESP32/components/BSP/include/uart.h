#ifndef _UART_H
#define _UART_H

#ifdef __cplusplus
extern "C"
{
#endif

#include "stdio.h"

#define TXD_PIN         (GPIO_NUM_26)
#define RXD_PIN         (GPIO_NUM_27)

#define UART_NUM        UART_NUM_1

void uart_init(void);
void uart_task(void);
void uart_tx_task(uint8_t *data, int len);
uint16_t CRC16Calculate(uint8_t* data, uint16_t len);

#ifdef __cplusplus
}
#endif
#endif 
