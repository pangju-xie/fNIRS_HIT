/**********************************************************************
Copyright ? LIZ MEDICAL TECHNOLOGY Co., Ltd. 2022. All rights reserved.
�ļ���		: utils.h
����	  	: ����Ϊ <458386139@qq.com>
�汾	   	: V1.0
����	   	: ͨ�����
����	   	: ��
��־	   	: ����V1.0 2024/8/14 ����Ϊ����
***********************************************************************/
#include "utils.h"
#include "main.h"
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include "stdarg.h"
#include "utils.h"
#include "stm32f4xx.h"
#include "stm32f4xx_hal.h"
#include "usart.h"

#define DEBUG

static uint8_t crc_table[256];

volatile uint8_t SendDoneDebugUART = 1;

uint32_t getUs(void)
{
	uint32_t usTicks = HAL_RCC_GetSysClockFreq() / 1000000;
	register uint32_t ms, cycle_cnt;
	do {
		ms = HAL_GetTick();
		cycle_cnt = SysTick->VAL;
	} while (ms != HAL_GetTick());

	return (ms * 1000) + (usTicks * 1000 - cycle_cnt) / usTicks;
}

void user_delay_us(uint32_t micros)
{
	uint32_t start = getUs();

	while (getUs()-start < (uint32_t) micros)
	{
	//	__nop();
	}
}
//΢�뼶��ʱ����
void Delay_us(uint32_t udelay)
{
	uint32_t startval,tickn,delays,wait;
 
  startval = SysTick->VAL;
  tickn = HAL_GetTick();
  //sysc = 72000;  //SystemCoreClock / (1000U / uwTickFreq);
  delays =udelay * 144; //sysc / 1000 * udelay;
  if(delays > startval){
		while(HAL_GetTick() == tickn){}
		wait = 144000 + startval - delays;
		while(wait < SysTick->VAL){}
	}
  else{
		wait = startval - delays;
		while(wait < SysTick->VAL && HAL_GetTick() == tickn){}
	}
}

/*************************************************
 * @description			:	8λcrc���������
 * @param - data		:	���ݵ�ַ
 * @param - len			:	���ݳ���
 * @return 				:	8λcrc������
**************************************************/
uint8_t crc_8bit(uint8_t data[], uint8_t len)
{
	uint16_t crc = 0;
	int i = 0;
	int j = 0;

	for (i = 0; i < len; i++)
	{
		crc ^= data[i] << 8;
		for (j = 0; j < 8; j++)
		{
			if (crc & 0x8000)
				crc ^= (0xd5 << 7);
			crc <<= 1;
		}
	}

	return ((crc >> 8) & 0xFF);
}

void GenerateTable(uint8_t poly){
	for(int i = 0; i<256;++i){
		int curr = i;
		for(uint8_t j = 0; j<8;++j){
			if((curr &0x80) != 0){
				curr = curr << 1^((int)poly);
			}
			else{
				curr<<=1;
			}
		}
		crc_table[i] =(uint8_t)curr;
	}
	return;
}



uint8_t crc_8bit_fast(uint8_t data[], int len){
	uint8_t crc = 0;
	for(int i = 0;i<len;i++){
		crc = crc_table[crc^data[i]];
	}
	return crc;
}

void reverseArray(uint8_t *data, int size){
	int start = 0;
	int end = size-1;
	
	while(start<end){
		uint8_t temp = data[start];
		data[start] = data[end];
		data[end] = temp;
		start++;
		end--;
	}
}

enum {
	DBG_REDIR_OFT_HEAD = 0,
	DBG_REDIR_OFT_CMD = 2,
	DBG_REDIR_OFT_LEN = 3,
	DBG_REDIR_OFT_VALUE_LVL = 4,
	DBG_REDIR_OFT_VALUE_INFO = 5,
};
#define UART_MSG_CRC_TAIL_LEN 3
#define UART_MSG_HEAD 0x2325
#define UART_MSG_TAIL 0x0D0A
#define STM32_DBG_INFO_SIZE 128
#define UART_CMD_DBG_REDIR 0xC1

/*************************************************
 * @description			:	��Ϣ�ض���esp32����
 * @param - level		:	���Դ�ӡ�ȼ�
 * @param - format		:	��ӡ��ʽ
 * @return 				:	��
**************************************************/
void DebugPrintf(char * format, ...)
{
	#ifdef DEBUG
	uint8_t DELAY = 100;
	va_list args;
	int info_len = 0;
	char send_buf[STM32_DBG_INFO_SIZE] = {0};

	va_start(args, format);
	info_len = vsnprintf(send_buf, STM32_DBG_INFO_SIZE, format, args);
	va_end(args);
	if (0 > info_len)
	{
		return;
	}
	info_len += 1;	/* ����ĩβ'0' */
	
	while(DELAY-- ){
		if(SendDoneDebugUART){
			SendDoneDebugUART = 0;
			if(HAL_OK == HAL_UART_Transmit_DMA(&DEBUG_UART, (uint8_t *)send_buf, info_len)){
				return ;
			}
		}
	}
	#endif
}

int fputc(int ch, FILE *f)
 
{
 
  HAL_UART_Transmit(&DEBUG_UART, (uint8_t *)&ch, 1, 0xffff);
 
  return ch;
 
}
