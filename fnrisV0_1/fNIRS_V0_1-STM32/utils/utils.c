/**********************************************************************
Copyright ? LIZ MEDICAL TECHNOLOGY Co., Ltd. 2022. All rights reserved.
文件名		: utils.h
作者	  	: 刘有为 <458386139@qq.com>
版本	   	: V1.0
描述	   	: 通用组件
其他	   	: 无
日志	   	: 初版V1.0 2024/8/14 刘有为创建
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
//微秒级延时函数
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
 * @description			:	8位crc检验码计算
 * @param - data		:	数据地址
 * @param - len			:	数据长度
 * @return 				:	8位crc检验码
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
 * @description			:	信息重定向到esp32串口
 * @param - level		:	调试打印等级
 * @param - format		:	打印格式
 * @return 				:	无
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
	info_len += 1;	/* 算上末尾'0' */
	
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
