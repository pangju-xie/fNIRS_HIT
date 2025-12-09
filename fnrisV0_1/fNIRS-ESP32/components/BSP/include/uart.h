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

// 帧协议定义
#define UART_RX_BUF_SIZE    400    // UART接收缓冲区大小
#define UART_TEMP_BUF_SIZE  200     // UART临时读取缓冲区大小
void uart_init(void);
void uart_task(void);
void uart_tx_task(uint8_t *data, int len);
uint16_t CRC16Calculate(uint8_t* data, uint16_t len);

#ifdef __cplusplus
}
#endif
#endif 
