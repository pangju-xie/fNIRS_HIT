#ifndef __TRANSMIT__H
#define __TRANSMIT__H

#include "stdio.h"
#include "stdint.h"
#include "usart.h"
#include "spi.h"

#define T_SPI									hspi2
#define T_UART								huart3

#define UART_ENABLE(uart)				__HAL_UART_ENABLE_IT(&uart, UART_IT_IDLE);
#define UART_DISABLE(uart)			__HAL_UART_DISABLE_IT(&uart, UART_IT_IDLE);

#define SPI_CS_LOW					HAL_GPIO_WritePin(WIFI_CS_GPIO_Port, WIFI_CS_Pin, GPIO_PIN_RESET)
#define SPI_CS_HIGH					HAL_GPIO_WritePin(WIFI_CS_GPIO_Port, WIFI_CS_Pin, GPIO_PIN_SET)
#define CRC16_POLY							0x1021

#define DOWNHEADER								0xABAB
#define UPHEADER									0xBABA

#define TXBUFSIZE				1024
#define RXBUFSIZE				256

#define CMD_PLACE					6
#define DLEN_PLACE				7
#define DATA_PLACE				9
#define FRAME_LEN					11

typedef enum{
	EEG						=	1,
	EMG 					=	2,
	EEG_EMG				=	3,
	fNIRS					=	4,
	EEG_fNIRS			=	5,
	EEG_fNIRS_EMG	=	7,
	NIRS					=	8,
}SENSOR_TYPE;

typedef enum{
	CMD_CONN 					= 0xB0,
	CMD_DISC 					= 0xB1,
	CMD_START					= 0xC0,
	CMD_STOP 					= 0xC1,
	CMD_VBAT 					= 0xC2,
	CMD_SPR  					= 0xC3,
	CMD_CFGC 					= 0xA0,
	CMD_DATA 					= 0xA1,
	CMD_SUPP 					= 0xA2,
}T_COMMAND;

typedef struct{
	uint8_t type;
	uint8_t spr;
}SAMPLE_RATE;

typedef struct{
	uint8_t buf[RXBUFSIZE];
	int index;
	uint8_t flag;
}UART_RxBuf;

extern UART_RxBuf uart_rx;

HAL_StatusTypeDef UartTransmitDMA(uint8_t *data, uint32_t len, uint32_t delay_time);
HAL_StatusTypeDef SPITransmitDMA(uint8_t *data, uint32_t len, uint32_t delay_time);

void GetSensorID(void);
void InitDataBuf(uint8_t *buf, SENSOR_TYPE stype, T_COMMAND cmd, uint16_t len);
void DataFrameSwitchCMD(uint8_t *buf, T_COMMAND cmd);
void DataFrameInit(void);
void DecodeCommand(uint8_t* data, int len);
void EncodeCommand(T_COMMAND cmd, uint8_t data);

void EncodeData(uint8_t* src, uint8_t* data, uint8_t len);

int RxReady(void);

void GenerateCRC16Table(uint16_t poly);
uint16_t CRC16Calculate(uint8_t* data, uint16_t len);

#endif
